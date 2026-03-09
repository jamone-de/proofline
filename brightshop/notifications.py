"""Customer e-mail texts. Subjects are picked by name: _subject_<kind>."""
from datetime import timedelta

from .customers import is_b2b_customer
from .money import format_money

GERMAN_SPEAKING = ("DE", "AT", "CH")


def language_for(country):
    return "de" if country in GERMAN_SPEAKING else "en"


def greeting(customer):
    """Formal for business and for Austria and Switzerland, informal for German consumers."""
    lang = language_for(customer.country)
    formal = is_b2b_customer(customer) or customer.country in ("AT", "CH")
    if lang == "de":
        return ("Sehr geehrte Damen und Herren, %s" if formal else "Hallo %s,") % customer.name
    return "Dear %s," % customer.name


def dispatch_day(placed_on):
    """Orders are packed on the next working day, weekends roll to Monday."""
    day = placed_on + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def _subject_order_confirmation(order, lang):
    if lang == "de":
        return "Ihre Bestellung %s bei Brightshop" % order.number
    return "Your Brightshop order %s" % order.number


def _subject_shipping(order, lang):
    if lang == "de":
        return "Bestellung %s ist unterwegs" % order.number
    return "Order %s is on its way" % order.number


def _subject_reminder(order, lang):
    if lang == "de":
        return "Zahlungserinnerung zu Bestellung %s" % order.number
    return "Payment reminder for order %s" % order.number


def build_email(kind, order, customer, today, reminder=None):
    """Return {"to", "subject", "body"} for the given kind of message."""
    lang = language_for(customer.country)
    subject = globals()["_subject_" + kind](order, lang)
    lines = [greeting(customer), ""]
    total = format_money(order.totals["gross_cents"])
    if kind == "order_confirmation":
        lines.append("vielen Dank für Ihre Bestellung über %s." % total if lang == "de"
                     else "thank you for your order of %s." % total)
        if order.shipping_method == "pickup":
            lines.append("Ihre Ware liegt ab morgen zur Abholung bereit." if lang == "de"
                         else "Your goods are ready for pickup from tomorrow.")
        else:
            ship = dispatch_day(order.placed_on)
            lines.append("Versand voraussichtlich am %s." % ship.strftime("%d.%m.%Y") if lang == "de"
                         else "Expected dispatch on %s." % ship.isoformat())
        if order.placed_on.weekday() >= 5:
            lines.append("Bestellungen am Wochenende werden am Montag bearbeitet." if lang == "de"
                         else "Weekend orders are processed on Monday.")
    elif kind == "shipping":
        carrier = order.totals["shipping"].get("carrier") or "our carrier"
        lines.append("Ihr Paket wurde an %s übergeben." % carrier if lang == "de"
                     else "your parcel was handed to %s." % carrier)
    else:
        level = reminder["level"] if reminder else 1
        fee = reminder["fee_cents"] if reminder else 0
        lines.append("dies ist Mahnstufe %d." % level if lang == "de" else "this is reminder %d." % level)
        if fee:
            lines.append("Mahngebühr: %s" % format_money(fee) if lang == "de"
                         else "Reminder fee: %s" % format_money(fee))
    lines += ["", "Brightshop" if lang == "en" else "Ihr Brightshop-Team"]
    return {"to": customer.email, "subject": subject, "body": "\n".join(lines)}


def send_via_smtp(message, host="localhost"):
    """Delivery was outsourced to the mail provider. Never finished."""
    raise NotImplementedError("smtp delivery is not implemented")
