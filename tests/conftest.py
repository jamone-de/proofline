from datetime import date

import pytest

from brightshop.models import Customer, PricingContext, Product
from brightshop.store import Store


@pytest.fixture
def store():
    s = Store()
    s.add_product(Product("A-1", "Alpha", "electronics", 10000, 500), stock=10)
    s.add_product(Product("B-1", "Beta book", "books", 2000, 300, vat_class="reduced"), stock=3)
    s.add_product(Product("C-1", "Cable", "accessories", 500, 50), stock=0)
    return s


@pytest.fixture
def customer():
    return Customer(1, "Test Person", "DE", "test@example.com", tier="silver", since=date(2025, 1, 1))


@pytest.fixture
def ctx(store):
    return PricingContext(store=store, today=date(2026, 9, 16))
