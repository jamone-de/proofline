"""Shipping quotes: zones, weight brackets, carriers, surcharges."""
from . import config

ZONE_DE = "DE"
ZONE_EU = "EU"
ZONE_WORLD = "WORLD"

EU_ZONE_COUNTRIES = {"AT", "FR", "NL", "IT", "ES", "PL", "SE", "IE", "BE"}

# (max weight in grams, (DE, EU, WORLD) price in cents)
RATE_TABLE = [
    (500, (490, 990, 1990)),
    (2000, (590, 1290, 2490)),
    (5000, (790, 1690, 3490)),
    (10000, (1090, 2290, 4990)),
    (31500, (1990, 3990, 7990)),
]

FREE_SHIPPING_CENTS = {"DE": 7500, "EU": 15000}
FREIGHT_BASE_CENTS = 3900
FREIGHT_PER_10KG_CENTS = 1200


def zone_for(country):
    if country == "DE":
        return ZONE_DE
    if country in EU_ZONE_COUNTRIES:
        return ZONE_EU
    return ZONE_WORLD


def legacy_zone_lookup(country):
    """Flat per-country price from the 2019 table. Superseded by RATE_TABLE."""
    return config.LEGACY_SHIPPING_TABLE.get(country, 2990)


class Carrier:
    code = "?"
    priority = 99
    fuel_bp = 0

    def handles(self, zone, weight_g):
        return False


class CarrierDHL(Carrier):
    code = "DHL"
    priority = 1

    def handles(self, zone, weight_g):
        return zone in (ZONE_DE, ZONE_EU) and weight_g <= 20000


class CarrierDPD(Carrier):
    code = "DPD"
    priority = 2

    def handles(self, zone, weight_g):
        return zone in (ZONE_DE, ZONE_EU) and weight_g <= 31500


class CarrierUPS(Carrier):
    code = "UPS"
    priority = 3
    fuel_bp = 700

    def handles(self, zone, weight_g):
        return True


def pick_carrier(zone, weight_g):
    for cls in sorted(Carrier.__subclasses__(), key=lambda c: c.priority):
        carrier = cls()
        if carrier.handles(zone, weight_g):
            return carrier
    return Carrier()


def _quote_v2(weight_g, country, method):
    """Rate-shopping engine. Only reachable with ENABLE_NEW_SHIPPING_ENGINE."""
    carrier = pick_carrier(zone_for(country), weight_g)
    return {"carrier": carrier.code, "total_cents": 0, "method": method}


def _base_price(weight_g, zone_index):
    for max_weight, prices in RATE_TABLE:
        if weight_g <= max_weight:
            return prices[zone_index]
    return None


def quote_shipping(weight_g, country, method, goods_cents, placed_on, is_b2b=False):
    """Return a dict describing what shipping costs for this parcel."""
    if config.ENABLE_NEW_SHIPPING_ENGINE:
        return _quote_v2(weight_g, country, method)
    zone = zone_for(country)
    notes = []
    result = {
        "method": method, "zone": zone, "carrier": "", "base_cents": 0,
        "express_cents": 0, "weekend_cents": 0, "fuel_cents": 0,
        "freight_cents": 0, "free": False, "total_cents": 0, "notes": notes,
    }
    if weight_g <= 0:
        notes.append("no shippable goods")
        return result
    if method == "pickup":
        if zone == ZONE_DE:
            result["method"] = "pickup"
            notes.append("pickup in store")
            return result
        notes.append("pickup not available abroad, using standard")
        method = "standard"
        result["method"] = "standard"
    zone_index = {ZONE_DE: 0, ZONE_EU: 1, ZONE_WORLD: 2}[zone]
    base = _base_price(weight_g, zone_index)
    if base is None:
        # heavier than 31.5 kg: freight forwarding
        result["carrier"] = "FREIGHT"
        result["freight_cents"] = FREIGHT_BASE_CENTS + (weight_g // 10000) * FREIGHT_PER_10KG_CENTS
        base = 0
        notes.append("freight forwarding")
    else:
        carrier = pick_carrier(zone, weight_g)
        result["carrier"] = carrier.code
        if carrier.fuel_bp:
            result["fuel_cents"] = (base * carrier.fuel_bp + 5000) // 10000
    result["base_cents"] = base
    if method == "express":
        if zone == ZONE_WORLD:
            result["express_cents"] = base * 60 // 100 + 900
        else:
            result["express_cents"] = base * 80 // 100 + 600
        notes.append("express")
    elif method == "standard":
        threshold = FREE_SHIPPING_CENTS.get(zone)
        if threshold is not None and goods_cents >= threshold and not result["freight_cents"]:
            result["free"] = True
            notes.append("free shipping over %d" % (threshold // 100))
    if placed_on.weekday() >= 5 and method == "standard" and goods_cents < 20000:
        result["weekend_cents"] = 490
        notes.append("weekend handling")
    total = result["express_cents"] + result["weekend_cents"] + result["freight_cents"]
    if not result["free"]:
        total += base + result["fuel_cents"]
    result["total_cents"] = total
    return result
