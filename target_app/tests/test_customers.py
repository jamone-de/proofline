from datetime import date

from brightshop import customers
from brightshop.models import Customer


def make(**kw):
    base = dict(id=1, name="X", country="DE", email="x@example.com", since=date(2025, 1, 1))
    base.update(kw)
    return Customer(**base)


def test_tier_for_lifetime():
    assert customers.tier_for_lifetime(0) == "bronze"
    assert customers.tier_for_lifetime(150_000) == "silver"
    assert customers.tier_for_lifetime(1_500_000) == "platinum"


def test_b2b_detection():
    assert customers.is_b2b_customer(make(vat_id="DE123456789"))
    assert not customers.is_b2b_customer(make(is_business=True, lifetime_cents=999_999))
    assert not customers.is_b2b_customer(None)
