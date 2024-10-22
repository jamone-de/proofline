"""VAT rules: rates per country, exceptions, reverse charge, per-group tax."""
import re

from .money import round_div

STANDARD_RATES_BP = {
    "DE": 1900, "AT": 2000, "FR": 2000, "NL": 2100, "IT": 2100,
    "ES": 2100, "PL": 2300, "SE": 2500, "IE": 2300, "BE": 2100,
}

REDUCED_RATES_BP = {
    "DE": 700, "AT": 1000, "FR": 550, "NL": 900, "IT": 1000,
    "ES": 1000, "PL": 800, "SE": 1200, "IE": 1350, "BE": 600,
}

EU_COUNTRIES = frozenset(STANDARD_RATES_BP)

VAT_ID_PATTERNS = {
    "DE": r"DE[1-9]\d{8}",
    "AT": r"ATU\d{8}",
    "FR": r"FR[A-Z0-9]{2}\d{9}",
    "NL": r"NL\d{9}B\d{2}",
    "IE": r"IE\d[A-Z0-9+*]\d{5}[A-Z]{1,2}",
    "PL": r"PL\d{10}",
    "IT": r"IT\d{11}",
    "ES": r"ES[A-Z0-9]\d{7}[A-Z0-9]",
    "SE": r"SE\d{12}",
    "BE": r"BE0\d{9}",
}


def is_eu(country):
    return country in EU_COUNTRIES


def is_valid_vat_id(vat_id):
    if not vat_id:
        return False
    vat_id = vat_id.replace(" ", "").upper()
    pattern = VAT_ID_PATTERNS.get(vat_id[:2])
    if pattern is None:
        return False
    return re.fullmatch(pattern, vat_id) is not None


# Country specific exceptions. tax_rate_bp() looks these up by name:
# "vat_special_" + country code in lower case.
def vat_special_de(category):
    if category == "hygiene":
        return 700
    return None
