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

    return app
