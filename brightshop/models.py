"""Plain data containers and exceptions."""
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional

TIERS = ("bronze", "silver", "gold", "platinum")


class BrightshopError(Exception):
    pass


class PricingError(BrightshopError):
    pass


class StockError(BrightshopError):
    pass


@dataclass
class Product:
    sku: str
    name: str
    category: str
    price_cents: int
    weight_g: int
    vat_class: str = "standard"      # standard | reduced | zero
    active: bool = True
    clearance: bool = False


@dataclass
class Customer:
    id: int
    name: str
    country: str
    email: str
    vat_id: Optional[str] = None
    tier: str = "bronze"
    lifetime_cents: int = 0
    payment_terms: str = "prepaid"   # prepaid | net14 | net30
    is_business: bool = False
    loyalty_points: int = 0
    since: Optional[date] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class PricingContext:
    store: object
    today: date
    ship_country: str = "DE"
    shipping_method: str = "standard"
    coupon: Optional[str] = None
    mode: str = "sale"               # sale | return
    redeem_points: int = 0
