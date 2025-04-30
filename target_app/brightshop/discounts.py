"""Discount engine: volume breaks, bundles, loyalty tiers, coupons, caps."""
import sys

from . import config
from .money import percent_bp, round_div

LOYALTY_BP = {"bronze": 0, "silver": 300, "gold": 500, "platinum": 800}
LOYALTY_CAP_BP = {"bronze": 1500, "silver": 2000, "gold": 2500, "platinum": 2500}

# (minimum quantity, discount in bp), checked from the top
VOLUME_BREAKS = [(100, 1200), (25, 800), (10, 500)]

BUNDLE_SETS = [
    {"name": "Photo starter", "skus": ("CAM-100", "MEM-64", "BAG-01"), "percent_bp": 1000},
    {"name": "Desk light kit", "skus": ("LMP-200", "CBL-USB2"), "percent_bp": 800},
]

COUPONS = {
    "WELCOME10": {"rule": "first_order", "percent_bp": 1000, "min_cents": 3000},
    "SUMMER25": {"rule": "seasonal", "percent_bp": 2500, "min_cents": 5000,
                 "starts": "2026-06-01", "expires": "2026-08-31"},
    "AUTUMN15": {"rule": "seasonal", "percent_bp": 1500, "min_cents": 4000,
                 "starts": "2026-09-01", "expires": "2026-10-31"},
    "SAVE5": {"rule": "fixed", "fixed_cents": 300, "min_cents": 2500},
    "FREESHIP": {"rule": "freeship"},
    "VIP20": {"rule": "percent", "percent_bp": 2000, "min_cents": 10000},
}

HAPPY_HOUR_RULES = [
    {"weekday": 4, "from_hour": 16, "to_hour": 18, "percent_bp": 500},
]


# --- coupon rules -------------------------------------------------------------
# Resolved by name in apply_discounts: "rule_" + coupon["rule"].
# Each returns (discount_cents, note, free_shipping).
def rule_percent(coupon, base_cents, info):
    if base_cents < coupon.get("min_cents", 0):
        return 0, "coupon minimum not reached", False
    return percent_bp(base_cents, coupon["percent_bp"]), "coupon", False


def rule_first_order(coupon, base_cents, info):
    if info["previous_orders"] > 0:
        return 0, "coupon only valid for a first order", False
    return rule_percent(coupon, base_cents, info)


def rule_seasonal(coupon, base_cents, info):
    today = info["today"].isoformat()
    if today < coupon["starts"] or today > coupon["expires"]:
        return 0, "coupon not valid on this date", False
    return rule_percent(coupon, base_cents, info)


def rule_fixed(coupon, base_cents, info):
    if base_cents < coupon.get("min_cents", 0):
        return 0, "coupon minimum not reached", False
    return min(coupon["fixed_cents"], base_cents), "coupon", False


def rule_freeship(coupon, base_cents, info):
    return 0, "free shipping coupon", True


def apply_coupon_stacking(lines, coupon_codes, base_cents):
    """Apply several coupons one after another. Behind ENABLE_COUPON_STACKING."""
    total = 0
    remaining = base_cents
    for code in coupon_codes:
        coupon = COUPONS.get(code)
        if coupon and "percent_bp" in coupon:
            amount = percent_bp(remaining, coupon["percent_bp"])
            total += amount
            remaining -= amount
    return total


def _spread(amount, weights):
    """Distribute `amount` over `weights` proportionally, remainder to the largest."""
    total = sum(weights)
    if total == 0 or amount == 0:
        return [0] * len(weights)
    shares = [round_div(amount * w, total) if total > 0 else 0 for w in weights]
    diff = amount - sum(shares)
    if diff:
        biggest = max(range(len(weights)), key=lambda i: abs(weights[i]))
        shares[biggest] += diff
    return shares


def apply_discounts(lines, customer, coupon_code, ctx):
    """Apply all discounts to `lines` and return (lines, summary).

    Order matters: volume, bundle, loyalty, coupon, then the tier cap.
    """
    lines = [dict(line, discount_cents=0, reasons=[]) for line in lines]
    summary = {
        "volume_cents": 0, "bundle_cents": 0, "loyalty_cents": 0,
        "coupon_cents": 0, "cap_cents": 0, "total_cents": 0,
        "free_shipping": False, "notes": [], "coupon": None, "bundle": None,
    }
    goods = sum(line["line_cents"] for line in lines)
    is_return = ctx.mode == "return"
    coupon = None
    if coupon_code:
        coupon = COUPONS.get(coupon_code.strip().upper())
        if coupon is None:
            summary["notes"].append("unknown coupon %s" % coupon_code)
        elif is_return:
            summary["notes"].append("coupons are ignored on returns")
            coupon = None

    # 1) volume breaks per line
    for line in lines:
        if line["clearance"]:
            continue
        qty = abs(line["qty"])
        pct = 0
        for threshold, bp in VOLUME_BREAKS:
            if qty >= threshold:
                pct = bp
                break
        if pct:
            amount = percent_bp(line["line_cents"], pct)
            if amount:
                line["discount_cents"] += amount
                line["reasons"].append("volume %d%%" % (pct // 100))
                summary["volume_cents"] += amount

    # 2) bundles: not with a coupon, not on lines that already have a volume discount
    if config.ENABLE_BUNDLES and coupon is None and not coupon_code:
        by_sku = {line["sku"]: line for line in lines}
        for bundle in BUNDLE_SETS:
            if all(sku in by_sku for sku in bundle["skus"]):
                members = [by_sku[sku] for sku in bundle["skus"]]
                if any(m["discount_cents"] for m in members):
                    continue
                sets = min(abs(m["qty"]) for m in members)
                if sets > 0:
                    for member in members:
                        sign = -1 if member["qty"] < 0 else 1
                        amount = percent_bp(member["unit_cents"] * sets * sign, bundle["percent_bp"])
                        member["discount_cents"] += amount
                        member["reasons"].append("bundle %s" % bundle["name"])
                        summary["bundle_cents"] += amount
                    summary["bundle"] = bundle["name"]

    # 3) loyalty tier, never on clearance lines
    bp = LOYALTY_BP.get(customer.tier, 0) if customer is not None else 0
    if bp:
        for line in lines:
            if line["clearance"]:
                continue
            amount = percent_bp(line["line_cents"] - line["discount_cents"], bp)
            if amount:
                line["discount_cents"] += amount
                line["reasons"].append("loyalty %s" % customer.tier)
                summary["loyalty_cents"] += amount

    # 4) happy hour (marketing wanted it, then it was cancelled)
    if config.ENABLE_HAPPY_HOUR:
        for rule in HAPPY_HOUR_RULES:
            if ctx.today.weekday() == rule["weekday"]:
                extra = percent_bp(goods, rule["percent_bp"])
                summary["notes"].append("happy hour %d" % extra)

    # 5) coupon on what is left
    if coupon is not None:
        base = goods
        if summary["volume_cents"] and not config.ENABLE_COUPON_STACKING:
            summary["notes"].append("coupon not combinable with volume discount")
        else:
            handler = getattr(sys.modules[__name__], "rule_" + coupon["rule"], None)
            if handler is None:
                summary["notes"].append("coupon rule missing")
            else:
                previous = 0
                if customer is not None:
                    previous = len([o for o in ctx.store.orders_for_customer(customer.id)
                                    if o.status != "cancelled" and o.placed_on < ctx.today])
                info = {"today": ctx.today, "previous_orders": previous}
                amount, note, free_ship = handler(coupon, base, info)
                summary["notes"].append(note)
                if free_ship:
                    summary["free_shipping"] = True
                if amount:
                    weights = [line["line_cents"] - line["discount_cents"] for line in lines]
                    for line, share in zip(lines, _spread(amount, weights)):
                        if share:
                            line["discount_cents"] += share
                            line["reasons"].append("coupon %s" % coupon_code.strip().upper())
                    summary["coupon_cents"] = amount
                    summary["coupon"] = coupon_code.strip().upper()

    # 6) tier cap: total discounts may not exceed a share of the goods value
    total = (summary["volume_cents"] + summary["bundle_cents"]
             + summary["loyalty_cents"] + summary["coupon_cents"])
    cap_bp = LOYALTY_CAP_BP.get(customer.tier, 1500) if customer is not None else 1500
    cap = percent_bp(abs(goods), cap_bp)
    if goods < 0:
        cap = -cap
    if abs(total) > abs(cap) and total != 0:
        removed = 0
        for line in lines:
            if line["discount_cents"]:
                scaled = round_div(line["discount_cents"] * cap, total)
                removed += line["discount_cents"] - scaled
                line["discount_cents"] = scaled
                line["reasons"].append("capped")
        summary["cap_cents"] = removed
        summary["notes"].append("discount capped at %d%%" % (cap_bp // 100))
        total = total - removed

    summary["total_cents"] = total
    return lines, summary
