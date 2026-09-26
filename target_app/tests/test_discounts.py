from brightshop import discounts


def test_spread_keeps_total():
    shares = discounts._spread(100, [1, 1, 1])
    assert sum(shares) == 100
