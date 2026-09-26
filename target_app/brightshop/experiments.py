"""Price A/B testing framework (2024 experiment).

Was meant to be wired into pricing.calculate_order_total. The experiment
was cancelled before launch and nothing imports this module.
"""
import zlib

EXPERIMENTS = {
    "free-ship-70": {"variant_b_threshold_cents": 7000, "share_percent": 50},
    "charm-prices": {"variant_b_suffix": 99, "share_percent": 20},
}


def bucket_for(customer_id, experiment):
    """Stable A/B bucket from the customer id."""
    share = EXPERIMENTS[experiment]["share_percent"]
    return "B" if zlib.crc32(("%s:%s" % (experiment, customer_id)).encode()) % 100 < share else "A"


def free_ship_threshold(customer_id, default_cents):
    if bucket_for(customer_id, "free-ship-70") == "B":
        return EXPERIMENTS["free-ship-70"]["variant_b_threshold_cents"]
    return default_cents


def charm_price(customer_id, unit_cents):
    if bucket_for(customer_id, "charm-prices") == "B":
        return unit_cents // 100 * 100 + EXPERIMENTS["charm-prices"]["variant_b_suffix"]
    return unit_cents


class ExperimentLog:
    def __init__(self):
        self.events = []

    def record(self, customer_id, experiment, outcome):
        self.events.append((customer_id, experiment, outcome))

    def conversion(self, experiment):
        rows = [e for e in self.events if e[1] == experiment]
        if not rows:
            return 0.0
        return sum(1 for e in rows if e[2] == "converted") / len(rows)
