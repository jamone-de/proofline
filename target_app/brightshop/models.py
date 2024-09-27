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
