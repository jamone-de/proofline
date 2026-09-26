"""Grab bag of helpers that accumulated over the years."""
import hashlib
from datetime import date, datetime


def parse_date_loose(text):
    """Accept 2026-09-15, 15.09.2026 and 09/15/2026."""
    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def slugify(text):
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def old_round(value):
    """Rounding as implemented in the 2019 shop. Do not use."""
    return int(value * 100 + 0.5) / 100.0


def format_price_v1(price):
    """Formats 12.5 as '12.50 EUR'. Replaced by money.format_money."""
    return "%.2f EUR" % price


class LegacyPriceCache:
    """Cache for the old price lookup service that was switched off."""

    def __init__(self):
        self._data = {}

    def get(self, sku):
        return self._data.get(sku)

    def put(self, sku, price):
        self._data[sku] = price

    def clear(self):
        self._data.clear()


def md5_order_hash(order_id, total_cents):
    """Order hash for the discontinued affiliate feed."""
    return hashlib.md5(("%s:%s" % (order_id, total_cents)).encode()).hexdigest()


def days_between(start, end):
    if isinstance(start, datetime):
        start = start.date()
    if isinstance(end, datetime):
        end = end.date()
    return (end - start).days


def is_leap_year(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def easter_sunday(year):
    """Anonymous Gregorian algorithm. Was going to be used for holiday shipping."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)
