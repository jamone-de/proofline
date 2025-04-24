"""Fax gateway for sending invoices to customers without e-mail.

Switched off in 2023 when the last fax customer moved to PDF. The provider
credentials were removed, the module stayed. See docs/accounting-export.md.
"""
from .money import format_money

FAX_PROVIDER = "telefax-dienst"
RETRY_LIMIT = 3


def build_fax_cover(invoice, customer):
    return "\n".join([
        "TO: %s" % customer.name,
        "RE: invoice %s" % invoice.number,
        "AMOUNT: %s" % format_money(invoice.gross_cents),
    ])


def send_invoice_fax(invoice, customer, number):
    """Pretend to send. There is no provider behind this any more."""
    attempts = 0
    while attempts < RETRY_LIMIT:
        attempts += 1
        if number.startswith("+49"):
            return {"provider": FAX_PROVIDER, "attempts": attempts, "ok": True}
    return {"provider": FAX_PROVIDER, "attempts": attempts, "ok": False}
