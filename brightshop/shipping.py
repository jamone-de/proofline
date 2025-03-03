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

FREE_SHIPPING_CENTS = {"DE": 6000, "EU": 15000}
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
