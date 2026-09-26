import pytest

from brightshop import pricing
from brightshop.models import PricingError


def test_empty_cart_is_rejected(customer, ctx):
    with pytest.raises(PricingError):
        pricing.calculate_order_total([], customer, ctx)
