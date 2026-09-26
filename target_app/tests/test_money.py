import pytest

from brightshop import money


def test_round_div_positive_rounds_half_up():
    assert money.round_div(5, 2) == 3
    assert money.round_div(4, 3) == 1
    assert money.round_div(7, 3) == 2


def test_round_div_negative_rounds_half_toward_zero():
    assert money.round_div(-5, 2) == -2
    assert money.round_div(-7, 3) == -2
    assert money.round_div(-8, 3) == -3


def test_round_div_rejects_bad_denominator():
    with pytest.raises(ValueError):
        money.round_div(1, 0)


def test_percent_bp():
    assert money.percent_bp(10000, 1900) == 1900
    assert money.percent_bp(999, 1000) == 100


@pytest.mark.parametrize("text,cents", [("12,50", 1250), ("12.5", 1250), ("1.234,56", 123456), (7, 700)])
def test_to_cents(text, cents):
    assert money.to_cents(text) == cents


def test_to_cents_rejects_garbage():
    with pytest.raises(ValueError):
        money.to_cents("abc")


def test_format_money():
    assert money.format_money(123456) == "1.234,56 \u20ac"
    assert money.format_money(-5, symbol=False) == "-0,05"


def test_split_evenly_gives_remainder_to_first_shares():
    assert money.split_evenly(100, 3) == [34, 33, 33]
    assert sum(money.split_evenly(-100, 3)) == -100


def test_split_evenly_needs_parts():
    with pytest.raises(ValueError):
        money.split_evenly(100, 0)


def test_clamp():
    assert money.clamp(5, 1, 3) == 3
    assert money.clamp(-1, 1, 3) == 1
