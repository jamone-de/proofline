"""Discount engine: volume breaks, bundles, loyalty tiers, coupons, caps."""
import sys

from . import config
from .money import percent_bp, round_div

LOYALTY_BP = {"bronze": 0, "silver": 300, "gold": 400, "platinum": 800}
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
