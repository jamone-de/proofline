"""Flask admin UI. All business logic lives outside this package."""
from datetime import date

from flask import Flask, Response, abort, jsonify, redirect, render_template, request, url_for

from .. import config, customers, inventory, invoicing, notifications, pricing, reporting, seed, tax
from ..clock import FixedClock
from ..legacy_utils import parse_date_loose, slugify
from ..models import BrightshopError, PricingContext
from ..money import format_money
from . import helpers

COUNTRIES = ["DE", "AT", "FR", "NL", "IT", "ES", "PL", "SE", "IE", "BE", "CH", "GB", "US"]
METHODS = ["standard", "express", "pickup"]
REPORT_GROUPS = ["month", "week", "day", "category", "country", "customer"]


def create_app(store=None, today=None):
    app = Flask(__name__)
    clock = FixedClock(today)
    if store is None:
        store = seed.build_store(clock.today())
    app.config["STORE"] = store
    app.config["CLOCK"] = clock

    @app.template_filter("money")
    def money_filter(cents):
        return format_money(cents)

    @app.template_filter("datefmt")
    def date_filter(value):
        return value.strftime("%d %b %Y") if value else ""

    @app.template_filter("rate")
    def rate_filter(rate_bp):
        return tax.describe_rate(rate_bp)

    @app.template_filter("tone")
    def tone_filter(name):
        return helpers.status_tone(name)

    @app.template_filter("slug")
    def slug_filter(text):
        return slugify(text)

    @app.context_processor
    def inject_globals():
        return {"today": clock.today(), "shop_country": config.SHOP_COUNTRY}

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok", "today": clock.today().isoformat()})

    @app.route("/")
    def dashboard():
        today = clock.today()
        recent = sorted(store.orders.values(), key=lambda o: (o.placed_on, o.id), reverse=True)[:8]
        return render_template(
            "dashboard.html", kpis=reporting.kpis(store, today),
            chart=helpers.bar_chart(reporting.revenue_by_week(store, today)),
            recent=recent, top=reporting.top_customers(store, 5),
            reminders=reporting.overdue_reminders(store, today)[:3],
            reorder=inventory.reorder_suggestions(store, today)[:2],
            customers=store.customers, receivables=reporting.open_receivables(store, today),
            active="dashboard")

    @app.route("/orders")
    def orders():
        status = request.args.get("status", "")
        query = request.args.get("q", "").strip().lower()
        rows = sorted(store.orders.values(), key=lambda o: (o.placed_on, o.id), reverse=True)
        counts = {name: 0 for name in helpers.ORDER_STATUSES}
        for order in rows:
            counts[order.status] += 1
        if status:
            rows = [o for o in rows if o.status == status]
        if query:
            rows = [o for o in rows if query in o.number.lower()
                    or query in store.customers[o.customer_id].name.lower()]
        return render_template("orders.html", orders=rows, customers=store.customers,
                               statuses=helpers.ORDER_STATUSES, status=status, q=query,
                               counts=counts, total=len(store.orders), active="orders")

    @app.route("/orders/<int:order_id>")
    def order_detail(order_id):
        order = store.orders.get(order_id)
        if order is None:
            abort(404)
        return render_template(
            "order_detail.html", order=order, customer=store.customers[order.customer_id],
            invoices=store.invoices_for_order(order.id), today=clock.today(),
            email=notifications.build_email(
                "order_confirmation" if order.status in ("open", "paid") else "shipping",
                order, store.customers[order.customer_id], clock.today()),
            status_of=invoicing.invoice_status, active="orders")

    @app.route("/orders/<int:order_id>/invoice")
    def order_invoice(order_id):
        found = store.invoices_for_order(order_id)
        if not found:
            abort(404)
        return redirect(url_for("invoice_view", number=found[0].number))

    @app.route("/invoices/<number>")
    def invoice_view(number):
        invoice = store.invoices.get(number)
        if invoice is None:
            abort(404)
        order = store.orders[invoice.order_id]
        return render_template(
            "invoice.html", invoice=invoice, order=order,
            customer=store.customers[invoice.customer_id],
            status=invoicing.invoice_status(invoice, clock.today()), active="orders")

    def _calculation_inputs(source):
        """Read calculator inputs from a form, query string or JSON body."""
        getter = source.get
        customer_id = getter("customer_id") or ""
        customer = store.customers.get(int(customer_id)) if str(customer_id).isdigit() else None
        placed = parse_date_loose(getter("date") or "") or clock.today()
        ctx = PricingContext(
            store=store, today=placed, ship_country=getter("country") or (customer.country if customer else "DE"),
            shipping_method=getter("method") or "standard", coupon=(getter("coupon") or "").strip() or None,
            mode=getter("mode") or "sale", redeem_points=helpers.safe_int(getter("points"), 0))
        return customer, ctx

    @app.route("/calculator", methods=["GET", "POST"])
    def calculator():
        if request.method == "POST":
            form = request.form
            cart = helpers.parse_cart(form)
        else:
            form = {"customer_id": "1", "country": "DE", "method": "standard", "coupon": "",
                    "mode": "sale", "points": "0", "date": clock.today().isoformat()}
            cart = [{"sku": "CAM-100", "qty": 1}, {"sku": "MEM-64", "qty": 1}, {"sku": "BAG-01", "qty": 1}]
        customer, ctx = _calculation_inputs(form)
        result = None
        error = None
        try:
            result = pricing.calculate_order_total(cart, customer, ctx)
        except BrightshopError as exc:
            error = str(exc)
        return render_template(
            "calculator.html", products=sorted(store.products.values(), key=lambda p: p.sku),
            customers=sorted(store.customers.values(), key=lambda c: c.name), cart=cart,
            form=form, result=result, error=error, countries=COUNTRIES, methods=METHODS,
            active="calculator")

    @app.route("/api/calculate", methods=["POST"])
    def api_calculate():
        body = request.get_json(silent=True) or {}
        cart = body.get("cart") or []
        customer, ctx = _calculation_inputs(body)
        try:
            return jsonify(pricing.calculate_order_total(cart, customer, ctx))
        except BrightshopError as exc:
            return jsonify({"error": str(exc)}), 422

    @app.route("/api/invoices/<number>")
    def api_invoice(number):
        invoice = store.invoices.get(number)
        if invoice is None:
            abort(404)
        return jsonify({"number": invoice.number, "kind": invoice.kind, "issued_on": invoice.issued_on.isoformat(),
                        "due_on": invoice.due_on.isoformat(), "net_cents": invoice.net_cents,
                        "tax_cents": invoice.tax_cents, "gross_cents": invoice.gross_cents,
                        "tax_groups": invoice.tax_groups, "notes": invoice.notes,
                        "skonto_cents": invoice.skonto_cents})

    @app.route("/api/kpis")
    def api_kpis():
        return jsonify(reporting.kpis(store, clock.today()))

    @app.route("/customers")
    def customer_list():
        query = request.args.get("q", "")
        rows = customers.search_customers(store, query)
        counts = {c.id: len(store.orders_for_customer(c.id)) for c in rows}
        segments = {c.id: customers.customer_segment(c, counts[c.id]) for c in rows}
        return render_template("customers.html", rows=rows, counts=counts, segments=segments,
                               q=query, active="customers")

    @app.route("/customers/<int:customer_id>")
    def customer_detail(customer_id):
        customer = store.customers.get(customer_id)
        if customer is None:
            abort(404)
        orders_ = sorted(store.orders_for_customer(customer_id), key=lambda o: o.id, reverse=True)
        return render_template(
            "customer_detail.html", customer=customer, orders=orders_,
            invoices=store.invoices_for_customer(customer_id),
            segment=customers.customer_segment(customer, len(orders_)),
            credit=customers.credit_limit_cents(customer, store, clock.today()),
            tier_review=customers.recompute_tier(customer),
            b2b=customers.is_b2b_customer(customer), today=clock.today(),
            status_of=invoicing.invoice_status, active="customers")

    def _report_from_args():
        group_by = request.args.get("group_by", "month")
        start = parse_date_loose(request.args.get("start", "")) or date(clock.today().year, 1, 1)
        end = parse_date_loose(request.args.get("end", "")) or clock.today()
        if group_by not in REPORT_GROUPS:
            abort(400)
        return group_by, start, end, reporting.build_sales_report(store, start, end, group_by=group_by)

    return app
