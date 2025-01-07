"""Invoices, credit notes, payment terms and dunning."""
from datetime import timedelta

from . import config, pricing, tax
from .customers import is_b2b_customer
from .legacy_utils import days_between
from .models import BrightshopError, Invoice, PricingContext
from .money import format_money, percent_bp, round_div

DUE_DAYS = {"prepaid": 0, "net14": 14, "net30": 30}
REMINDER_DAYS = (10, 20, 30)      # days after the due date for reminder 1, 2, 3
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
