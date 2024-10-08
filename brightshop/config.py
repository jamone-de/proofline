"""Central configuration, feature flags and business constants.

Most numbers that drive pricing live here. Some do not (see pricing.py).
"""
import os

SHOP_COUNTRY = "DE"
CURRENCY = "EUR"

# The "current" date of the whole app. Never read from the wall clock so that
# every run produces the same numbers.
DEFAULT_TODAY = os.environ.get("BRIGHTSHOP_TODAY", "2026-09-15")

# --- feature flags -----------------------------------------------------------
ENABLE_BUNDLES = True
ENABLE_SKONTO = True
ENABLE_PROMO_PRICES = True
ENABLE_COUPON_STACKING = False          # never switched on in production
ENABLE_LOYALTY_DOUBLE_POINTS = False    # campaign ended, flag stayed
ENABLE_NEW_SHIPPING_ENGINE = False      # v2 engine was never finished
ENABLE_HAPPY_HOUR = False               # marketing idea from 2024

# Consulted only by the abandoned v1 shipping lookup.
LEGACY_SHIPPING_TABLE = {
    "DE": 490,
    "AT": 790,
    "CH": 1490,
    "FR": 890,
    "US": 2490,
}

# Business constants that are (mostly) used from more than one place.
B2B_LIST_DISCOUNT_BP = 500
B2B_VOLUME_THRESHOLD_CENTS = 10_000_00
MAX_LINE_QTY = 100
