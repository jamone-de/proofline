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
