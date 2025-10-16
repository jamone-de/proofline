"""Deterministic demo data. Same input, same shop, every time."""
from datetime import date, timedelta

from . import config, invoicing, pricing, returns
from .clock import FixedClock
from .models import Customer, Order, PricingContext, PricingError, Product
from .store import Store

# sku, name, category, price cents, weight g, vat class, clearance, active, stock
PRODUCTS = [
    ("CAM-100", "Lumen X1 Camera", "electronics", 44900, 620, "standard", False, True, 14),
    ("MEM-64", "SnapCard 64 GB", "electronics", 1990, 10, "standard", False, True, 120),
    ("BAG-01", "Lumen Camera Bag", "electronics", 5990, 480, "standard", False, True, 22),
    ("TRI-30", "Tripod Lite", "electronics", 3490, 900, "standard", False, True, 9),
    ("DRN-9", "Sky Mini Drone", "electronics", 27900, 750, "standard", False, True, 3),
    ("LMP-200", "Aurora Desk Lamp", "home", 5490, 1100, "standard", False, True, 31),
    ("LMP-300", "Aurora Floor Lamp", "home", 12990, 4800, "standard", False, True, 6),
    ("BLB-6", "Bright Bulb 6-pack", "home", 1290, 300, "standard", False, True, 80),
    ("CBL-USB2", "USB-C Cable 2 m", "accessories", 690, 60, "standard", False, True, 4),
    ("CHG-65", "65 W Charger", "accessories", 3490, 180, "standard", False, True, 44),
    ("CSE-PH", "Phone Case", "accessories", 1990, 40, "standard", False, True, 0),
    ("HUB-7", "7-Port Hub", "accessories", 4290, 210, "standard", False, True, 17),
    ("SPK-BT1", "Pebble Speaker", "audio", 7990, 650, "standard", False, True, 25),
    ("HDP-NC", "Quiet Headphones", "audio", 19900, 380, "standard", False, True, 11),
    ("MIC-USB", "Studio Mic", "audio", 8990, 540, "standard", False, True, 7),
    ("KTL-15", "Glow Kettle", "kitchen", 4990, 1400, "standard", False, True, 19),
    ("BLN-90", "Whirl Blender", "kitchen", 8990, 3100, "standard", False, True, 5),
    ("SCL-KIT", "Precise Scale", "kitchen", 2490, 520, "standard", False, True, 28),
    ("BK-LIGHT", "The Art of Light", "books", 3490, 850, "reduced", False, True, 40),
    ("BK-DATA", "Numbers at Work", "books", 2990, 700, "reduced", False, True, 35),
    ("BK-KID", "Little Lamps", "books", 1490, 300, "reduced", False, True, 60),
    ("HYG-01", "Care Pack", "hygiene", 1290, 200, "standard", False, True, 70),
    ("KID-TEE", "Kids Tee", "kids_clothing", 1990, 150, "standard", False, True, 33),
    ("KID-JKT", "Kids Jacket", "kids_clothing", 4990, 500, "standard", False, True, 12),
    ("DIG-LIC", "Photo Suite Licence", "digital", 9900, 0, "standard", False, True, 0),
    ("DIG-EBK", "Lighting E-Book", "digital", 1290, 0, "standard", False, True, 0),
    ("CLR-LMP", "Vintage Lamp (clearance)", "clearance", 2499, 900, "standard", True, True, 8),
    ("CLR-CSE", "Old Camera Case (clearance)", "clearance", 549, 250, "standard", True, True, 15),
    ("OLD-CAM", "Lumen X0 Camera", "electronics", 29900, 600, "standard", False, False, 2),
]

# id, name, country, vat id, tier, lifetime cents, terms, business, points, since
CUSTOMERS = [
    (1, "Nora Fischer", "DE", None, "silver", 214000, "prepaid", False, 640, date(2024, 11, 3)),
    (2, "Tobias Klein", "DE", None, "bronze", 45000, "prepaid", False, 90, date(2026, 2, 14)),
    (3, "Lea Brandt", "DE", None, "gold", 612000, "prepaid", False, 2210, date(2023, 5, 21)),
    (4, "Mira Stein", "AT", None, "silver", 188000, "prepaid", False, 410, date(2025, 1, 9)),
    (5, "Jonas Vogel", "DE", None, "platinum", 1820000, "net14", False, 5800, date(2022, 8, 30)),
    (6, "Elise Marchand", "FR", None, "bronze", 32000, "prepaid", False, 40, date(2026, 5, 2)),
    (7, "Pieter de Wit", "NL", None, "silver", 176000, "prepaid", False, 300, date(2025, 3, 17)),
    (8, "Sofia Romano", "IT", None, "bronze", 12900, "prepaid", False, 10, date(2026, 7, 28)),
    (9, "Hellwig Elektro GmbH", "DE", "DE123456789", "gold", 940000, "net30", True, 1200, date(2023, 1, 12)),
    (10, "Alpenlicht GmbH", "AT", "ATU12345678", "silver", 380000, "net30", True, 700, date(2024, 4, 4)),
    (11, "Atelier Moreau SARL", "FR", "FR12345678901", "gold", 720000, "net30", True, 980, date(2023, 9, 9)),
    (12, "Windmolen BV", "NL", "NL123456789B01", "silver", 410000, "net14", True, 350, date(2024, 6, 1)),
    (13, "Dublin Lighting Ltd", "IE", "IE1A23456B", "bronze", 95000, "net30", True, 120, date(2025, 10, 2)),
    (14, "Studio Polska sp. z o.o.", "PL", "PL1234567890", "silver", 260000, "net30", True, 0, date(2024, 12, 12)),
    (15, "Svensson Foto AB", "SE", "SE123456789012", "bronze", 88000, "net14", True, 60, date(2025, 8, 19)),
    (16, "Zurich Optik AG", "CH", None, "silver", 1240000, "net30", True, 0, date(2023, 3, 3)),
    (17, "London Lens Ltd", "GB", None, "gold", 2050000, "net30", True, 0, date(2022, 11, 25)),
    (18, "Bay Camera Co", "US", None, "bronze", 300000, "prepaid", True, 0, date(2025, 6, 6)),
    (19, "Anton Weber", "DE", None, "bronze", 8900, "prepaid", False, 0, date(2026, 8, 30)),
    (20, "Clara Neumann", "DE", None, "silver", 155000, "prepaid", False, 500, date(2025, 2, 2)),
    (21, "Oskar Lindqvist", "SE", None, "bronze", 22000, "prepaid", False, 20, date(2026, 4, 11)),
    (22, "Fiona Byrne", "IE", None, "silver", 190000, "prepaid", False, 280, date(2025, 5, 23)),
    (23, "Marek Nowak", "PL", None, "bronze", 41000, "prepaid", False, 30, date(2026, 1, 15)),
    (24, "Greta Lorenz", "DE", None, "gold", 530000, "net14", False, 1900, date(2023, 7, 7)),
]

COUPON_POOL = ["WELCOME10", "SAVE5", "FREESHIP", "VIP20", "AUTUMN15", "SUMMER25", ""]


class Lcg:
    """Tiny linear congruential generator so the seed never depends on random."""

    def __init__(self, seed):
        self.state = seed

    def next(self):
        self.state = (self.state * 1103515245 + 12345) % (2 ** 31)
        return self.state

    def below(self, n):
        return (self.next() >> 8) % n

    def chance(self, percent):
        return self.below(100) < percent

    def pick(self, seq):
        return seq[self.below(len(seq))]


def build_products(store):
    for sku, name, category, price, weight, vat_class, clearance, active, stock in PRODUCTS:
        store.add_product(Product(sku, name, category, price, weight, vat_class, active, clearance), stock)


def build_customers(store):
    for cid, name, country, vat_id, tier, lifetime, terms, business, points, since in CUSTOMERS:
        email = name.lower().replace(" ", ".").replace(",", "").replace("..", ".") + "@example.com"
        store.add_customer(Customer(cid, name, country, email, vat_id, tier, lifetime,
                                    terms, business, points, since))


def _status_for(age_days, rng):
    if age_days <= 1:
        return "open"
    if age_days <= 3:
        return "paid"
    if age_days <= 10:
        return "shipped"
    roll = rng.below(100)
    if roll < 4:
        return "cancelled"
    if roll < 9:
        return "returned"
    return "delivered"


def build_orders(store, today, count=110, seed=20260915):
    rng = Lcg(seed)
    skus = [p[0] for p in PRODUCTS if p[7]]
    favourites = ["CAM-100", "MEM-64", "BAG-01", "LMP-200", "CBL-USB2", "SPK-BT1", "BK-LIGHT"]
    start = date(2025, 10, 2)
    span = (today - start).days
    cids = sorted(store.customers)
    previous = start
    for i in range(count):
        placed = start + timedelta(days=span * (i + 1) * (3 * count - (i + 1)) // (2 * count * count) - rng.below(2))
        placed = min(max(placed, previous), today)
        previous = placed
        customer = store.customers[rng.pick(cids)]
        cart = []
        for _ in range(1 + rng.below(3)):
            sku = rng.pick(favourites) if rng.chance(45) else rng.pick(skus)
            qty = 1 + rng.below(3)
            if customer.is_business and rng.chance(30):
                qty = rng.pick([10, 12, 25, 30])
            cart.append({"sku": sku, "qty": qty})
        if rng.chance(20):
            cart.extend([{"sku": "CAM-100", "qty": 1}, {"sku": "MEM-64", "qty": 1},
                         {"sku": "BAG-01", "qty": 1}])
        coupon = rng.pick(COUPON_POOL) if rng.chance(35) else ""
        method = "standard"
        if rng.chance(15):
            method = "express"
        elif customer.country == "DE" and rng.chance(10):
            method = "pickup"
        points = 0
        if customer.tier != "bronze" and customer.loyalty_points >= 500 and rng.chance(12):
            points = 500
        ctx = PricingContext(store=store, today=placed, ship_country=customer.country,
                             shipping_method=method, coupon=coupon or None, redeem_points=points)
        try:
            totals = pricing.calculate_order_total(cart, customer, ctx)
        except PricingError:
            ctx = PricingContext(store=store, today=placed, ship_country=customer.country,
                                 shipping_method=method)
            totals = pricing.calculate_order_total(cart, customer, ctx)
        status = _status_for((today - placed).days, rng)
        order = Order(id=store.next_order_id(), number="", customer_id=customer.id,
                      placed_on=placed, lines=totals["lines"], coupon=ctx.coupon,
                      shipping_method=method, ship_country=customer.country,
                      status=status, totals=totals)
        order.number = "ORD-%d" % order.id
        store.add_order(order)


def build_invoices(store, today, seed=77):
    rng = Lcg(seed)
    for order in sorted(store.orders.values(), key=lambda o: o.id):
        if order.status in ("open", "cancelled"):
            continue
        customer = store.customers[order.customer_id]
        invoice = invoicing.generate_invoice(order, customer, store, order.placed_on)
        age = (today - invoice.due_on).days
        if customer.payment_terms == "prepaid":
            invoicing.record_payment(invoice, invoice.gross_cents, order.placed_on)
        elif age < 0:
            if rng.chance(30):
                pay_day = order.placed_on + timedelta(days=3 + rng.below(8))
                invoicing.record_payment(invoice, invoice.gross_cents, pay_day)
        elif rng.chance(100 if age > 75 else 90 if age > 35 else 55):
            pay_day = invoice.due_on + timedelta(days=rng.below(12) - 8)
            invoicing.record_payment(invoice, invoice.gross_cents, min(pay_day, today))
        if order.status == "returned":
            return_day = order.placed_on + timedelta(days=9)
            wanted = [{"sku": line["sku"], "qty": 1} for line in order.lines]
            decision = returns.evaluate_return(order, customer, store, return_day, wanted)
            if decision["accepted"]:
                invoicing.create_credit_note(order, customer, store, return_day,
                                             returns.refund_cart(decision)[:1])
