"""Invoices, credit notes, payment terms and dunning."""
from datetime import timedelta

from . import config, pricing, tax
from .customers import is_b2b_customer
from .legacy_utils import days_between
from .models import BrightshopError, Invoice, PricingContext
from .money import format_money, percent_bp, round_div

DUE_DAYS = {"prepaid": 0, "net14": 14, "net30": 30}
REMINDER_DAYS = (7, 21, 35)      # days after the due date for reminder 1, 2, 3
GERMAN_SPEAKING = ("DE", "AT", "CH")


def next_invoice_number(store, year, kind="invoice"):
    """BS-2026-00001 for invoices, CN-2026-00001 for credit notes. Resets yearly."""
    prefix = "BS" if kind == "invoice" else "CN"
    count = 0
    for existing in store.invoices.values():
        if existing.kind == kind and existing.number.split("-")[1] == str(year):
            count += 1
    return "%s-%d-%05d" % (prefix, year, count + 1)


def _render_footer_de(invoice):
    return "Zahlbar bis %s. Vielen Dank für Ihren Einkauf bei Brightshop." % invoice.due_on.strftime("%d.%m.%Y")


def _render_footer_en(invoice):
    return "Payable by %s. Thank you for shopping at Brightshop." % invoice.due_on.isoformat()


def render_invoice_text_v0(invoice):
    """Plain text rendering from the fax era."""
    rows = ["INVOICE " + invoice.number]
    for line in invoice.lines:
        rows.append("%3d x %-30s %10s" % (line["qty"], line["description"][:30], format_money(line["net_cents"])))
    rows.append("TOTAL " + format_money(invoice.gross_cents))
    return "\n".join(rows)


def generate_invoice(order, customer, store, today, kind="invoice", totals=None, lang=None):
    """Turn an order (or a return calculation) into an Invoice and store it."""
    if order.status in ("cancelled", "open") and kind == "invoice":
        raise BrightshopError("order %s cannot be invoiced in status %s" % (order.number, order.status))
    totals = totals if totals is not None else order.totals
    if lang is None:
        lang = "de" if order.ship_country in GERMAN_SPEAKING else "en"
    b2b = is_b2b_customer(customer)
    reverse = tax.is_reverse_charge(order.ship_country, customer)

    lines = []
    groups = {}
    for src in totals["lines"]:
        if reverse:
            rate = 0
        else:
            rate = tax.tax_rate_bp(order.ship_country, src["vat_class"], src["category"])
        description = src["name"]
        if src["discount_cents"]:
            if lang == "de":
                description += " (abzgl. Rabatt)"
            else:
                description += " (discount applied)"
        lines.append({"description": description, "sku": src["sku"], "qty": src["qty"],
                      "unit_cents": src["unit_cents"], "discount_cents": src["discount_cents"],
                      "net_cents": src["net_cents"], "rate_bp": rate})
        groups[rate] = groups.get(rate, 0) + src["net_cents"]
    dominant = max(groups.items(), key=lambda kv: (abs(kv[1]), kv[0]))[0]
    if totals["shipping_cents"]:
        lines.append({"description": "Versand" if lang == "de" else "Shipping", "sku": "",
                      "qty": 1, "unit_cents": totals["shipping_cents"], "discount_cents": 0,
                      "net_cents": totals["shipping_cents"], "rate_bp": dominant})
        groups[dominant] += totals["shipping_cents"]
    if totals["surcharge_cents"]:
        lines.append({"description": "Mindermengenzuschlag" if lang == "de" else "Small order surcharge",
                      "sku": "", "qty": 1, "unit_cents": totals["surcharge_cents"],
                      "discount_cents": 0, "net_cents": totals["surcharge_cents"], "rate_bp": dominant})
        groups[dominant] += totals["surcharge_cents"]

    tax_groups = []
    net_total = 0
    tax_total = 0
    for rate in sorted(groups, reverse=True):
        group_tax = round_div(groups[rate] * rate, 10000)
        tax_groups.append({"rate_bp": rate, "net_cents": groups[rate], "tax_cents": group_tax})
        net_total += groups[rate]
        tax_total += group_tax

    terms = customer.payment_terms if customer is not None else "prepaid"
    days = DUE_DAYS.get(terms, 0)
    due = today + timedelta(days=days)
    if days:
        # due dates never fall on a weekend, push to Monday
        if due.weekday() == 5:
            due += timedelta(days=2)
        elif due.weekday() == 6:
            due += timedelta(days=1)

    skonto_until = None
    skonto_cents = 0
    if config.ENABLE_SKONTO and kind == "invoice" and terms == "net30" and b2b:
        skonto_until = today + timedelta(days=10)
        skonto_cents = percent_bp(net_total + tax_total, 300)

    notes = []
    if reverse:
        if lang == "de":
            notes.append("Steuerschuldnerschaft des Leistungsempfängers (Reverse Charge)")
        else:
            notes.append("Reverse charge: VAT to be accounted for by the recipient")
    elif not tax.is_eu(order.ship_country):
        if lang == "de":
            notes.append("Steuerfreie Ausfuhrlieferung")
        else:
            notes.append("Tax free export delivery")
    if kind == "credit_note":
        notes.append("Gutschrift zu Bestellung %s" % order.number if lang == "de"
                     else "Credit note for order %s" % order.number)
    if skonto_cents:
        notes.append("2%% skonto (%s) until %s" % (format_money(skonto_cents), skonto_until.isoformat()))

    invoice = Invoice(
        number=next_invoice_number(store, today.year, kind), order_id=order.id,
        customer_id=order.customer_id, issued_on=today, due_on=due, kind=kind,
        lines=lines, tax_groups=tax_groups, net_cents=net_total, tax_cents=tax_total,
        gross_cents=net_total + tax_total, language=lang, notes=notes,
        skonto_until=skonto_until, skonto_cents=skonto_cents,
    )
    footer = globals().get("_render_footer_" + lang) or _render_footer_en
    invoice.footer = footer(invoice)
    store.add_invoice(invoice)
    return invoice


def create_credit_note(order, customer, store, today, return_cart):
    """Credit note for returned goods. Amounts are negative."""
    ctx = PricingContext(store=store, today=today, ship_country=order.ship_country,
                         shipping_method=order.shipping_method, mode="return")
    totals = pricing.calculate_order_total(return_cart, customer, ctx)
    return generate_invoice(order, customer, store, today, kind="credit_note", totals=totals)


def record_payment(invoice, cents, paid_on):
    invoice.paid_cents += cents
    invoice.paid_on = paid_on
    if invoice.skonto_until and paid_on <= invoice.skonto_until:
        if invoice.paid_cents >= invoice.gross_cents - invoice.skonto_cents:
            invoice.paid_cents = invoice.gross_cents
            invoice.notes.append("skonto granted")
    return invoice


def invoice_status(invoice, today):
    if invoice.kind == "credit_note":
        return "credit"
    if invoice.paid_cents >= invoice.gross_cents:
        return "paid"
    if today > invoice.due_on:
        return "overdue"
    if invoice.paid_cents:
        return "partial"
    return "open"


def reminder_level(days_overdue):
    level = 0
    for index, days in enumerate(REMINDER_DAYS, start=1):
        if days_overdue >= days:
            level = index
    return level


def reminder_fee(level, is_b2b):
    """Fee in cents. Level 3 is where it gets expensive."""
    if level <= 1:
        return 0
    if is_b2b:
        return 0 if level == 2 else 4000
    return 500 if level == 2 else 1000


def reminder_interest(open_cents, days_overdue, level, is_b2b):
    """Default interest, only charged from the third reminder on."""
    if level < 3:
        return 0
    rate_bp = 1200 if is_b2b else 800
    return round_div(open_cents * rate_bp * days_overdue, 10000 * 365)


def compute_reminder(invoice, customer, today):
    """What should be sent for this invoice today? None if nothing."""
    if invoice.kind != "invoice" or invoice.paid_cents >= invoice.gross_cents:
        return None
    overdue = days_between(invoice.due_on, today)
    if overdue <= 0:
        return None
    level = reminder_level(overdue)
    if level == 0 or level <= len(invoice.reminders):
        return None
    b2b = is_b2b_customer(customer)
    open_cents = invoice.gross_cents - invoice.paid_cents
    return {
        "level": level, "days_overdue": overdue,
        "fee_cents": reminder_fee(level, b2b),
        "interest_cents": reminder_interest(open_cents, overdue, level, b2b),
        "escalate": level >= 3,
    }
