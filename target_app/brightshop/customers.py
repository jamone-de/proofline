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


def points_for_order(gross_cents):
    """One point per full 2 EUR, at most 500 points per order."""
    points = gross_cents // 200
    if config.ENABLE_LOYALTY_DOUBLE_POINTS:
        points *= 2
    return clamp(points, 0, MAX_POINTS_PER_ORDER)


def award_points(customer, gross_cents):
    earned = points_for_order(gross_cents)
    customer.loyalty_points += earned
    return earned


def redeem_points(customer, points):
    if points > customer.loyalty_points:
        raise ValueError("not enough points")
    customer.loyalty_points -= points
    return points


def credit_limit_cents(customer, store, today):
    """Net-30 business customers get 10 % of their yearly volume, 1k to 25k EUR."""
    if not is_b2b_customer(customer) or customer.payment_terms != "net30":
        return 0
    year_ago = today.toordinal() - 365
    volume = 0
    for order in store.orders_for_customer(customer.id):
        if order.status != "cancelled" and order.placed_on.toordinal() >= year_ago:
            volume += order.totals.get("gross_cents", 0)
    return clamp(percent_bp(volume, 1000), 1_000_00, 25_000_00)
