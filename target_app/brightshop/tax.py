"""VAT rules: rates per country, exceptions, reverse charge, per-group tax."""
import re

from .money import round_div

STANDARD_RATES_BP = {
    "DE": 1900, "AT": 2000, "FR": 2000, "NL": 2100, "IT": 2200,
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


def vat_special_ie(category):
    if category == "kids_clothing":
        return 0
    return None


def vat_special_pl(category):
    if category == "books":
        return 500
    return None


def tax_rate_bp(country, vat_class="standard", category=""):
    """VAT rate in basis points for a delivery to `country`."""
    if country not in EU_COUNTRIES:
        return 0                      # exports are zero-rated
    if vat_class == "zero":
        return 0
    hook = globals().get("vat_special_" + country.lower())
    if hook is not None:
        special = hook(category)
        if special is not None:
            return special
    if vat_class == "reduced":
        return REDUCED_RATES_BP[country]
    return STANDARD_RATES_BP[country]


def is_reverse_charge(ship_country, customer):
    """B2B deliveries to a valid foreign EU VAT id are taxed by the buyer."""
    vat_id = getattr(customer, "vat_id", None)
    if not is_valid_vat_id(vat_id):
        return False
    vat_id = vat_id.replace(" ", "").upper()
    if vat_id[:2] == "DE":
        return False
    return is_eu(ship_country) and ship_country == vat_id[:2]


def compute_tax(net_cents, rate_bp):
    return round_div(net_cents * rate_bp, 10_000)


def tax_for_lines(lines, country, reverse_charge=False):
    """Tax per rate group. Each group is rounded once, not per line."""
    groups = {}
    for line in lines:
        rate = 0 if reverse_charge else tax_rate_bp(
            country, line.get("vat_class", "standard"), line.get("category", ""))
        groups[rate] = groups.get(rate, 0) + line["net_cents"]
    result = []
    for rate in sorted(groups, reverse=True):
        result.append({
            "rate_bp": rate,
            "net_cents": groups[rate],
            "tax_cents": compute_tax(groups[rate], rate),
        })
    return result


def describe_rate(rate_bp):
    if rate_bp == 0:
        return "0 %"
    text = "{:.2f}".format(rate_bp / 100).rstrip("0").rstrip(".")
    return text.replace(".", ",") + " %"


def vat_moss_rate_2015(country):
    """Mini One Stop Shop rate table from the 2015 digital goods reform."""
    table = {"AT": 2000, "FR": 2000, "NL": 2100, "IT": 2200, "ES": 2100}
    return table.get(country, 1900)
