"""Integer-cent money helpers.

All amounts in Brightshop are integers in cents. Rates are in basis points
(1 bp = 0.01 %). This module is small on purpose and has good test coverage.
"""

from decimal import Decimal, InvalidOperation


def round_div(numerator, denominator):
    """Divide two integers and round to the nearest integer.

    Positive results round half up. Negative results (credit notes, returns)
    round half toward zero, so a refund never exceeds the original charge.
    """
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    quotient, remainder = divmod(abs(numerator), denominator)
    if numerator >= 0:
        return quotient + (1 if remainder * 2 >= denominator else 0)
    return -(quotient + (1 if remainder * 2 > denominator else 0))


def percent_bp(cents, basis_points):
    """Take `basis_points` of `cents`, rounded with round_div."""
    return round_div(cents * basis_points, 10_000)


def to_cents(value):
    """Parse '12,50', '12.50', 12.5 or 12 (euros) into 1250 cents."""
    if isinstance(value, int):
        return value * 100
    text = str(value).strip().replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ValueError("not a money amount: %r" % (value,))
    return int((amount * 100).to_integral_value(rounding="ROUND_HALF_UP"))


def format_money(cents, symbol=True):
    """German number format: 1.234,56 EUR sign."""
    sign = "-" if cents < 0 else ""
    euros, rest = divmod(abs(cents), 100)
    text = "{:,}".format(euros).replace(",", ".") + "," + "%02d" % rest
    return sign + text + (" €" if symbol else "")


def split_evenly(total, parts):
    """Split `total` cents into `parts` shares; the first shares get the remainder."""
    if parts <= 0:
        raise ValueError("parts must be positive")
    base, extra = divmod(abs(total), parts)
    shares = [base + (1 if i < extra else 0) for i in range(parts)]
    return shares if total >= 0 else [-s for s in shares]


def clamp(value, low, high):
    return max(low, min(high, value))
