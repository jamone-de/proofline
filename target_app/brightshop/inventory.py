"""Stock levels, reservations and reorder suggestions."""
import zlib

from .money import percent_bp

BACKORDER_LIMIT = -5
BACKORDER_CATEGORIES = {"accessories"}
PACK_SIZE = 5
COST_RATIO_BP = 6000          # purchase cost is 60 % of the list price

REORDER_POINTS = {"electronics": 5, "audio": 6, "home": 8, "kitchen": 8,
                  "books": 10, "accessories": 20, "hygiene": 12, "digital": 0,
                  "kids_clothing": 6, "clearance": 0}


def available(store, sku):
    return store.stock.get(sku, 0)


def can_backorder(product):
    return product.category in BACKORDER_CATEGORIES


def reorder_point(product):
    return REORDER_POINTS.get(product.category, 10)


def stock_status(store, sku):
    product = store.products[sku]
    free = available(store, sku)
    if product.category == "digital":
        return "unlimited"
    if free <= 0:
        return "out"
    if free <= reorder_point(product):
        return "low"
    return "ok"


def reserve(store, sku, qty):
    from .models import StockError
    product = store.products[sku]
    floor = BACKORDER_LIMIT if can_backorder(product) else 0
    if available(store, sku) - qty < floor:
        raise StockError("not enough stock for %s" % sku)
    store.stock[sku] -= qty
    return store.stock[sku]


def release(store, sku, qty):
    store.stock[sku] = available(store, sku) + qty
    return store.stock[sku]


def units_sold(store, sku, today, days=90):
    start = today.toordinal() - days
    total = 0
    for order in store.orders.values():
        if order.status in ("cancelled", "open") or order.placed_on.toordinal() < start:
            continue
        for line in order.lines:
            if line["sku"] == sku:
                total += line["qty"]
    return total


def reorder_suggestions(store, today, lead_time_days=14):
    """Suggest purchase quantities for everything that will run out in lead time."""
    suggestions = []
    for sku, product in sorted(store.products.items()):
        if not product.active or product.category == "digital" or product.clearance:
            continue
        sold = units_sold(store, sku, today)
        per_day_x100 = sold * 100 // 90
        need = per_day_x100 * (lead_time_days + 7) // 100
        free = available(store, sku)
        if free <= max(need, reorder_point(product)):
            wanted = max(need * 2 - free, PACK_SIZE * 2)
            wanted = ((wanted + PACK_SIZE - 1) // PACK_SIZE) * PACK_SIZE
            suggestions.append({"sku": sku, "name": product.name, "available": free,
                                "sold_90d": sold, "suggested": wanted})
    return suggestions


def stock_value_cents(store):
    total = 0
    for sku, qty in store.stock.items():
        if qty > 0:
            total += percent_bp(store.products[sku].price_cents, COST_RATIO_BP) * qty
    return total


def bin_for(sku, category):
    """Warehouse bin like E-17, derived from the sku so it never changes."""
    letter = (category or "x")[0].upper()
    return "%s-%02d" % (letter, zlib.crc32(sku.encode()) % 40 + 1)


class LegacyStockAdjuster:
    """Nightly adjustment job from the old ERP integration."""

    def __init__(self, store):
        self.store = store

    def adjust(self, sku, delta, reason="erp"):
        self.store.stock[sku] = available(self.store, sku) + delta
        return reason

    def bulk_adjust(self, deltas):
        for sku, delta in deltas.items():
            self.adjust(sku, delta)
