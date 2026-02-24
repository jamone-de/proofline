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
        growth = round((cur_total - prev_total) * 1000 / prev_total) / 10
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


def top_customers(store, limit=5):
    totals = {}
    for order in store.orders.values():
        if order.status in REVENUE_STATUSES:
            totals[order.customer_id] = totals.get(order.customer_id, 0) + order.totals["net_cents"]
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(store.customers[cid], cents) for cid, cents in ranked[:limit]]


def top_customers_v0(store):
    """First dashboard widget. Sorted by lifetime value only."""
    return sorted(store.customers.values(), key=lambda c: -c.lifetime_cents)[:5]


def open_receivables(store, today):
    """Open invoice amounts in aging buckets."""
    buckets = {"current": 0, "1_30": 0, "31_60": 0, "60_plus": 0}
    overdue = 0
    for inv in store.invoices.values():
        if inv.kind != "invoice" or inv.paid_cents >= inv.gross_cents:
            continue
        open_cents = inv.gross_cents - inv.paid_cents
        late = (today - inv.due_on).days
        if late <= 0:
            buckets["current"] += open_cents
        else:
            overdue += 1
            if late <= 30:
                buckets["1_30"] += open_cents
            elif late <= 60:
                buckets["31_60"] += open_cents
            else:
                buckets["60_plus"] += open_cents
    return {"buckets": buckets, "overdue_count": overdue, "total_cents": sum(buckets.values())}


def tax_forecast(store):
    """Expected VAT on orders that have no invoice yet."""
    invoiced = {inv.order_id for inv in store.invoices.values()}
    forecast = {}
    for order in store.orders.values():
        if order.id in invoiced or order.status in ("cancelled", "returned"):
            continue
        for group in tax.tax_for_lines(order.lines, order.ship_country, order.totals["reverse_charge"]):
            forecast[group["rate_bp"]] = forecast.get(group["rate_bp"], 0) + group["tax_cents"]
    return forecast


def category_breakdown(store, start, end):
    result = {}
    for order in _revenue_orders(store, start, end):
        for line in order.lines:
            result[line["category"]] = result.get(line["category"], 0) + line["net_cents"]
    return sorted(result.items(), key=lambda kv: -kv[1])


def build_sales_report(store, start, end, group_by="month", include_cancelled=False,
                       compare_previous=True):
    """Sales report grouped by day, week, month, category, country or customer."""
    if group_by not in ("day", "week", "month", "category", "country", "customer"):
        raise ValueError("unknown grouping %s" % group_by)
    statuses = list(REVENUE_STATUSES)
    if include_cancelled:
        statuses.append("cancelled")
    rows = {}
    for order in store.orders.values():
        if order.status not in statuses:
            continue
        if order.placed_on < start or order.placed_on > end:
            continue
        if group_by == "category":
            keys = []
            for line in order.lines:
                if line["category"] not in keys:
                    keys.append(line["category"])
        elif group_by == "day":
            keys = [order.placed_on.isoformat()]
        elif group_by == "week":
            iso = order.placed_on.isocalendar()
            keys = ["%d-W%02d" % (iso[0], iso[1])]
        elif group_by == "month":
            keys = [order.placed_on.strftime("%Y-%m")]
        elif group_by == "country":
            keys = [order.ship_country]
        else:
            keys = [store.customers[order.customer_id].name]
        for key in keys:
            row = rows.setdefault(key, {"key": key, "orders": 0, "units": 0,
                                        "net_cents": 0, "gross_cents": 0})
            row["orders"] += 1
            if group_by == "category":
                for line in order.lines:
                    if line["category"] == key:
                        row["units"] += line["qty"]
                        row["net_cents"] += line["net_cents"]
                row["gross_cents"] = row["net_cents"]
            else:
                row["units"] += sum(line["qty"] for line in order.lines)
                row["net_cents"] += order.totals["net_cents"]
                row["gross_cents"] += order.totals["gross_cents"]
    ordered = [rows[k] for k in sorted(rows)]
    for row in ordered:
        row["avg_cents"] = int(round(row["net_cents"] / row["orders"])) if row["orders"] else 0
    total_net = sum(r["net_cents"] for r in ordered)
    growth = None
    if compare_previous:
        span = (end - start).days + 1
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=span - 1)
        prev_total = 0
        for order in store.orders.values():
            if order.status in statuses and prev_start <= order.placed_on <= prev_end:
                prev_total += order.totals["net_cents"]
        if prev_total:
            growth = round((total_net - prev_total) * 1000 / prev_total) / 10
    return {"start": start, "end": end, "group_by": group_by, "rows": ordered,
            "total_net_cents": total_net,
            "total_orders": sum(r["orders"] for r in ordered) if group_by != "category" else None,
            "growth_pct": growth}


@exporter("csv")
def _export_csv(report):
    lines = ["key;orders;units;net;gross"]
    for row in report["rows"]:
        lines.append(";".join([row["key"], str(row["orders"]), str(row["units"]),
                               format_money(row["net_cents"], False),
                               format_money(row["gross_cents"], False)]))
    return "\n".join(lines) + "\n"


@exporter("json")
def _export_json(report):
    import json
    body = {"group_by": report["group_by"], "rows": report["rows"],
            "total_net_cents": report["total_net_cents"]}
    return json.dumps(body, sort_keys=True)


def export_report(report, fmt):
    handler = EXPORTERS.get(fmt)
    if handler is None:
        raise ValueError("no exporter for %s" % fmt)
    return handler(report)


def export_xml_report(report):
    """XML export for the accountant. See docs/accounting-export.md."""
    rows = "".join("<row key=\"%s\" net=\"%d\"/>" % (r["key"], r["net_cents"]) for r in report["rows"])
    return "<report>%s</report>" % rows


def overdue_reminders(store, today):
    """Reminders that are due today, as (invoice, reminder) pairs."""
    due = []
    for inv in sorted(store.invoices.values(), key=lambda i: i.number):
        customer = store.customers[inv.customer_id]
        reminder = invoicing.compute_reminder(inv, customer, today)
        if reminder:
            due.append((inv, reminder))
    return due


def batch_rows(rows, size=50):
    return list(chunked(rows, size))
