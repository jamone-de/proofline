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
