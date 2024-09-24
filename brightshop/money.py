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
    return -(quotient + (1 if remainder * 2 >= denominator else 0))


def percent_bp(cents, basis_points):
    """Take `basis_points` of `cents`, rounded with round_div."""
    return round_div(cents * basis_points, 10_000)
