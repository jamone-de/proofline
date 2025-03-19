"""Reporting: KPIs, sales reports, receivables and exporters."""
from datetime import timedelta

from . import inventory, invoicing, tax
from .legacy_utils import chunked
from .money import format_money

EXPORTERS = {}
REVENUE_STATUSES = ("paid", "shipped", "delivered")


def exporter(fmt):
    """Register a report exporter under a format name."""
    def register(func):
        EXPORTERS[fmt] = func
        return func
    return register


def _revenue_orders(store, start, end):
    return [o for o in store.orders.values()
            if o.status in REVENUE_STATUSES and start <= o.placed_on <= end]


def revenue_cents(store, start, end):
    return sum(o.totals["net_cents"] for o in _revenue_orders(store, start, end))


def average_order_value_cents(orders):
    """Average net order value. Uses float math and Python's round (half even)."""
    if not orders:
        return 0
    total = sum(o.totals["net_cents"] for o in orders)
    return int(round(total / len(orders)))


def kpis(store, today):
    start = today - timedelta(days=29)
    prev_start = today - timedelta(days=59)
    prev_end = today - timedelta(days=30)
    current = _revenue_orders(store, start, today)
    previous = _revenue_orders(store, prev_start, prev_end)
    cur_total = sum(o.totals["net_cents"] for o in current)
    prev_total = sum(o.totals["net_cents"] for o in previous)
    growth = None
    if prev_total:
        growth = (cur_total - prev_total) * 100 // prev_total
    receivables = open_receivables(store, today)
    low_stock = [sku for sku in store.products if inventory.stock_status(store, sku) in ("low", "out")]
    return {
        "revenue_30d_cents": cur_total,
        "revenue_growth_pct": growth,
        "orders_30d": len(current),
        "avg_order_cents": average_order_value_cents(current),
        "open_orders": len([o for o in store.orders.values() if o.status == "open"]),
        "receivables_cents": receivables["total_cents"],
        "overdue_count": receivables["overdue_count"],
        "low_stock_count": len(low_stock),
    }


def revenue_by_week(store, today, weeks=8):
    """Net revenue per ISO week for the last `weeks` weeks, oldest first."""
    buckets = []
    monday = today - timedelta(days=today.weekday())
    for i in range(weeks - 1, -1, -1):
        week_start = monday - timedelta(days=7 * i)
        week_end = week_start + timedelta(days=6)
        iso = week_start.isocalendar()
        buckets.append({
            "label": "W%02d" % iso[1], "start": week_start,
            "cents": revenue_cents(store, week_start, min(week_end, today)),
        })
    return buckets
