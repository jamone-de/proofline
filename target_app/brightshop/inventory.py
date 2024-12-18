"""Stock levels, reservations and reorder suggestions."""
import zlib

from .money import percent_bp

BACKORDER_LIMIT = -5
BACKORDER_CATEGORIES = {"accessories"}
PACK_SIZE = 5
COST_RATIO_BP = 5500          # purchase cost is 60 % of the list price

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
