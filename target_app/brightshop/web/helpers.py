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


def bar_chart(buckets, width=640, height=200, pad=28):
    """Geometry for a simple bar chart, rendered as inline SVG by the template."""
    peak = max([b["cents"] for b in buckets] + [1])
    count = max(len(buckets), 1)
    slot = (width - pad) / count
    bar_width = slot * 0.62
    usable = height - pad - 18
    bars = []
    for index, bucket in enumerate(buckets):
        bar_height = round(usable * bucket["cents"] / peak, 1)
        bars.append({
            "x": round(pad + index * slot + (slot - bar_width) / 2, 1),
            "y": round(height - pad - bar_height, 1),
            "w": round(bar_width, 1),
            "h": bar_height,
            "label": bucket["label"],
            "cx": round(pad + index * slot + slot / 2, 1),
            "cents": bucket["cents"],
            "last": index == count - 1,
            "short": ("%.1fk" % (bucket["cents"] / 100000)).replace(".", ",") if bucket["cents"] else "",
        })
    return {"bars": bars, "width": width, "height": height, "baseline": height - pad, "peak": peak}
