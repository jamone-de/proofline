"""View helpers for the web layer."""
from ..legacy_utils import safe_int

ORDER_STATUSES = ("open", "paid", "shipped", "delivered", "returned", "cancelled")

STATUS_TONES = {
    "open": "warn", "paid": "info", "shipped": "info", "delivered": "ok",
    "returned": "muted", "cancelled": "bad", "overdue": "bad", "partial": "warn",
    "credit": "muted", "ok": "ok", "low": "warn", "out": "bad", "unlimited": "muted",
    "bronze": "muted", "silver": "info", "gold": "gold", "platinum": "gold",
    "b2b": "info", "vip": "gold", "new": "ok", "regular": "muted",
}


def status_tone(name):
    return STATUS_TONES.get(name, "muted")


def format_legacy_date(value):
    """Old dashboard date format like 15/09/26."""
    return value.strftime("%d/%m/%y")


def parse_cart(form):
    """Build a cart from repeated sku/qty form fields, skipping empty rows."""
    cart = []
    for sku, qty in zip(form.getlist("sku"), form.getlist("qty")):
        amount = safe_int(qty, 0)
        if sku and amount > 0:
            cart.append({"sku": sku, "qty": amount})
    return cart
