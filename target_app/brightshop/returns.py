"""Return policy: windows, exclusions and restocking fees."""
from .customers import is_b2b_customer
from .money import percent_bp

RETURN_WINDOW_DAYS = {"consumer": 30, "business": 14}
NON_RETURNABLE_CATEGORIES = {"digital", "hygiene"}
RESTOCKING_CATEGORIES = {"electronics"}
RESTOCKING_FEE_BP = 1000
RESTOCKING_MIN_CENTS = 500


def return_window_days(customer):
    """Business customers only get two weeks, consumers a month."""
    return RETURN_WINDOW_DAYS["business" if is_b2b_customer(customer) else "consumer"]


def line_return_status(line, product, order, customer, today):
    """Return (accepted, reason) for one order line."""
    if product.category in NON_RETURNABLE_CATEGORIES:
        return False, "not returnable (%s)" % product.category
    if product.clearance:
        return False, "clearance items are final sale"
    if (today - order.placed_on).days > return_window_days(customer):
        return False, "return window of %d days is over" % return_window_days(customer)
    if order.status not in ("shipped", "delivered", "returned"):
        return False, "order was not delivered"
    return True, "ok"


def restocking_fee_cents(line, product, opened):
    """Opened electronics cost 10 % (at least 5 EUR) of the line value."""
    if not opened or product.category not in RESTOCKING_CATEGORIES:
        return 0
    fee = percent_bp(line["net_cents"], RESTOCKING_FEE_BP)
    return max(fee, RESTOCKING_MIN_CENTS)


def evaluate_return(order, customer, store, today, requested, opened_skus=()):
    """Decide which of the requested items may go back."""
    accepted = []
    rejected = []
    fee_total = 0
    by_sku = {line["sku"]: line for line in order.lines}
    for item in requested:
        line = by_sku.get(item["sku"])
        if line is None:
            rejected.append({"sku": item["sku"], "reason": "not part of the order"})
            continue
        product = store.products[item["sku"]]
        ok, reason = line_return_status(line, product, order, customer, today)
        if not ok:
            rejected.append({"sku": item["sku"], "reason": reason})
            continue
        qty = min(item["qty"], line["qty"])
        fee = restocking_fee_cents(line, product, item["sku"] in opened_skus)
        if qty < line["qty"] and fee:
            fee = fee * qty // line["qty"]
        accepted.append({"sku": item["sku"], "qty": qty, "fee_cents": fee})
        fee_total += fee
    return {"accepted": accepted, "rejected": rejected, "fee_cents": fee_total}


def refund_cart(evaluation):
    return [{"sku": item["sku"], "qty": item["qty"]} for item in evaluation["accepted"]]
