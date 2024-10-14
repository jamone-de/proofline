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
    "LMP-200": {"price_cents": 3990, "starts": "2026-09-01", "ends": "2026-08-31"},
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
