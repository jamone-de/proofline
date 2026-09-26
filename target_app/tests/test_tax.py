from types import SimpleNamespace

from brightshop import tax


def test_standard_and_reduced_rates():
    assert tax.tax_rate_bp("DE") == 1900
    assert tax.tax_rate_bp("DE", "reduced") == 700
    assert tax.tax_rate_bp("AT") == 2000


def test_non_eu_is_zero_rated():
    assert tax.tax_rate_bp("CH") == 0
    assert tax.tax_rate_bp("US", "reduced") == 0


def test_vat_id_validation():
    assert tax.is_valid_vat_id("DE123456789")
    assert not tax.is_valid_vat_id("DE023456789")
    assert not tax.is_valid_vat_id(None)


def test_reverse_charge_needs_foreign_valid_id():
    buyer = SimpleNamespace(vat_id="ATU12345678")
    assert tax.is_reverse_charge("AT", buyer)
    assert not tax.is_reverse_charge("DE", buyer)
    assert not tax.is_reverse_charge("AT", SimpleNamespace(vat_id="DE123456789"))


def test_compute_tax_rounds_negative_half_toward_zero():
    assert tax.compute_tax(1000, 1900) == 190
    assert tax.compute_tax(-1050, 1900) == -199
