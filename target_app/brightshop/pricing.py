"""Order pricing. calculate_order_total() is the heart of the shop.

Everything that touches a customer's money passes through here. Nobody dares
to split it up. It also contains a few rules that are not written down anywhere
else, see the comments in the function body.
"""
from . import config, discounts, inventory, shipping, tax
from .customers import is_b2b_customer
from .models import PricingError
from .money import percent_bp, round_div

PROMO_PRICES = {
    "LMP-200": {"price_cents": 3990, "starts": "2026-09-01", "ends": "2026-09-30"},
    "CBL-USB2": {"price_cents": 490, "starts": "2026-08-15", "ends": "2026-10-15"},
    "SPK-BT1": {"price_cents": 5990, "starts": "2026-01-01", "ends": "2026-01-31"},
}

PRICE_HOOKS = {}


def price_hook(kind):
    def register(func):
        PRICE_HOOKS.setdefault(kind, []).append(func)
        return func
    return register


@price_hook("clearance")
def _clearance_price_hook(product, unit_cents):
    """Clearance prices always end in 90 cents."""
    whole = unit_cents // 100
    if unit_cents % 100 <= 90:
        return whole * 100 + 90
    return (whole + 1) * 100 + 90


def calculate_order_total_v1(cart, customer, store):
    """First version of the total calculation, before discounts.py existed.

    Replaced by calculate_order_total(). Kept "for reference".
    """
    net = 0
    for item in cart:
        product = store.products[item["sku"]]
        net += product.price_cents * item["qty"]
    if customer is not None and customer.tier == "gold":
        net = net - net * 5 // 100
    tax_cents = net * 19 // 100
    return {"net_cents": net, "tax_cents": tax_cents, "gross_cents": net + tax_cents}


def calculate_order_total(cart, customer, ctx):
    """Price a cart: lines, discounts, points, surcharge, shipping and tax.

    `cart` is a list of {"sku", "qty"}, `ctx` a models.PricingContext. In
    "return" mode the quantities are positive in the cart and negated here.
    Returns a plain dict, see the bottom of the function.
    """
    if not cart:
        raise PricingError("empty cart")
    if ctx.mode not in ("sale", "return"):
        raise PricingError("unknown mode %s" % ctx.mode)
    merged = {}
    order = []
    for item in cart:
        sku = item["sku"]
        qty = int(item["qty"])
        if qty == 0:
            continue
        if qty < 0:
            raise PricingError("negative quantity for %s" % sku)
        if sku in merged:
            merged[sku] += qty
        else:
            merged[sku] = qty
            order.append(sku)
    if not merged:
        raise PricingError("empty cart")

    notes = []
    store = ctx.store
    b2b = is_b2b_customer(customer)
    today_iso = ctx.today.isoformat()
    lines = []
    weight = 0
    for sku in order:
        qty = merged[sku]
        product = store.products.get(sku)
        if product is None:
            raise PricingError("unknown sku %s" % sku)
        if qty > config.MAX_LINE_QTY:
            raise PricingError("quantity too large for %s" % sku)
        if not product.active:
            if ctx.mode == "sale":
                raise PricingError("%s is no longer sold" % sku)
            notes.append("%s is inactive but accepted as return" % sku)
        unit = product.price_cents
        price_kind = "list"
        if config.ENABLE_PROMO_PRICES:
            promo = PROMO_PRICES.get(sku)
            if promo is not None:
                if promo["starts"] <= today_iso <= promo["ends"]:
                    unit = promo["price_cents"]
                    price_kind = "promo"
        if product.clearance:
            for hook in PRICE_HOOKS.get("clearance", []):
                unit = hook(product, unit)
            price_kind = "clearance"
        if b2b:
            # promo and clearance prices are already the lowest price
            if price_kind == "list":
                unit = unit - percent_bp(unit, config.B2B_LIST_DISCOUNT_BP)
                price_kind = "b2b list"
        signed_qty = -qty if ctx.mode == "return" else qty
        if ctx.mode == "sale" and product.category != "digital":
            free = inventory.available(store, sku)
            if free < qty:
                if inventory.can_backorder(product) and free - qty >= inventory.BACKORDER_LIMIT:
                    notes.append("%s on backorder" % sku)
                else:
                    notes.append("%s low on stock (%d left)" % (sku, free))
        weight += product.weight_g * qty
        lines.append({
            "sku": sku, "name": product.name, "category": product.category,
            "vat_class": product.vat_class, "clearance": product.clearance,
            "qty": signed_qty, "unit_cents": unit, "price_kind": price_kind,
            "line_cents": unit * signed_qty,
        })
    goods_before = sum(line["line_cents"] for line in lines)

    lines, dsum = discounts.apply_discounts(lines, customer, ctx.coupon, ctx)
    notes.extend(dsum["notes"])
    goods_discount = dsum["total_cents"]
    for line in lines:
        line["net_cents"] = line["line_cents"] - line["discount_cents"]

    # Loyalty points: 100 points = 1 EUR, silver and up, at most 20 % of the net goods
    points_used = 0
    points_value = 0
    if ctx.redeem_points and customer is not None and ctx.mode == "sale":
        if customer.tier in ("silver", "gold", "platinum"):
            usable = min(ctx.redeem_points, customer.loyalty_points)
            usable -= usable % 100
            net_now = sum(line["net_cents"] for line in lines)
            max_value = percent_bp(net_now, 2000)
            if usable > max_value:
                usable = max_value - max_value % 100
            if usable > 0:
                total_weight = sum(line["net_cents"] for line in lines)
                shares = []
                for line in lines:
                    shares.append(round_div(usable * line["net_cents"], total_weight))
                shares[0] += usable - sum(shares)
                for line, share in zip(lines, shares):
                    line["net_cents"] -= share
                    line["discount_cents"] += share
                    if share:
                        line["reasons"].append("points")
                points_used = usable
                points_value = usable
                notes.append("redeemed %d points" % usable)
        else:
            notes.append("points can only be redeemed from tier silver")

    # Hard stop: discounts and points together may never exceed 35 % of the goods
    if goods_before > 0 and (goods_discount + points_value) * 100 > goods_before * 35:
        raise PricingError("total discount above 35 percent")

    net_goods = sum(line["net_cents"] for line in lines)

    surcharge = 0
    if ctx.mode == "sale" and not b2b and ctx.ship_country == config.SHOP_COUNTRY:
        if 0 < net_goods < 1000:
            surcharge = 250
            notes.append("small order surcharge")

    ship = {"total_cents": 0, "method": ctx.shipping_method, "carrier": "", "free": False,
            "base_cents": 0, "express_cents": 0, "weekend_cents": 0, "fuel_cents": 0,
            "freight_cents": 0, "zone": shipping.zone_for(ctx.ship_country), "notes": []}
    if ctx.mode == "sale":
        ship = shipping.quote_shipping(weight, ctx.ship_country, ctx.shipping_method,
                                       net_goods, ctx.today, b2b)
        if dsum["free_shipping"] and not ship["free"] and not ship["freight_cents"]:
            if ship["method"] != "pickup":
                ship["total_cents"] -= ship["base_cents"] + ship["fuel_cents"]
                ship["free"] = True
                notes.append("shipping free by coupon")
        notes.extend(ship["notes"])

    reverse = tax.is_reverse_charge(ctx.ship_country, customer)
    groups = {}
    for line in lines:
        if reverse:
            rate = 0
        else:
            rate = tax.tax_rate_bp(ctx.ship_country, line["vat_class"], line["category"])
        line["rate_bp"] = rate
        groups[rate] = groups.get(rate, 0) + line["net_cents"]
    if reverse:
        notes.append("reverse charge")
    # shipping and surcharge follow the rate of the biggest goods group
    dominant = max(groups.items(), key=lambda kv: (abs(kv[1]), kv[0]))[0]
    groups[dominant] += ship["total_cents"] + surcharge
    tax_groups = []
    tax_total = 0
    for rate in sorted(groups, reverse=True):
        group_tax = round_div(groups[rate] * rate, 10000)
        tax_groups.append({"rate_bp": rate, "net_cents": groups[rate], "tax_cents": group_tax})
        tax_total += group_tax

    net_total = net_goods + ship["total_cents"] + surcharge
    return {
        "mode": ctx.mode,
        "lines": lines,
        "goods_cents": goods_before,
        "discount_cents": goods_discount + points_value,
        "discounts": dsum,
        "net_goods_cents": net_goods,
        "surcharge_cents": surcharge,
        "shipping": ship,
        "shipping_cents": ship["total_cents"],
        "net_cents": net_total,
        "tax_groups": tax_groups,
        "tax_cents": tax_total,
        "gross_cents": net_total + tax_total,
        "points_used": points_used,
        "reverse_charge": reverse,
        "weight_g": weight,
        "b2b": b2b,
        "notes": notes,
    }
