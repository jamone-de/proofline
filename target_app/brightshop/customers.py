"""Customer rules: tiers, B2B status, loyalty points, credit limits."""
from . import config, tax
from .models import TIERS
from .money import clamp, percent_bp

# Lifetime spend (net, cents) needed for each tier, highest first.
TIER_THRESHOLDS = [
    ("platinum", 15_000_00),
    ("gold", 5_000_00),
    ("silver", 1_500_00),
    ("bronze", 0),
]

MAX_POINTS_PER_ORDER = 1000


def tier_for_lifetime(lifetime_cents):
    for name, threshold in TIER_THRESHOLDS:
        if lifetime_cents >= threshold:
            return name
    return "bronze"


def recompute_tier(customer):
    """Upgrade immediately, downgrade only one step at a time."""
    earned = tier_for_lifetime(customer.lifetime_cents)
    current = TIERS.index(customer.tier)
    target = TIERS.index(earned)
    if target < current:
        target = current - 1
    return TIERS[target]


def is_b2b_customer(customer):
    """A valid VAT id always counts. Business flagged buyers need 10k lifetime."""
    if customer is None:
        return False
    if tax.is_valid_vat_id(customer.vat_id):
        return True
    return customer.is_business and customer.lifetime_cents >= config.B2B_VOLUME_THRESHOLD_CENTS


def customer_segment(customer, order_count):
    if is_b2b_customer(customer):
        return "b2b"
    if customer.tier in ("gold", "platinum"):
        return "vip"
    if order_count <= 1:
        return "new"
    return "regular"
