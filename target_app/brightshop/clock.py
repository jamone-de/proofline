"""Injectable clock. The app never calls date.today()."""
from datetime import date

from . import config


class FixedClock:
    def __init__(self, today=None):
        if today is None:
            today = config.DEFAULT_TODAY
        if isinstance(today, str):
            today = date.fromisoformat(today)
        self._today = today

    def today(self):
        return self._today


def default_clock():
    return FixedClock()
