"""Benchmark croniter ``get_next``/``get_prev`` (PR kiorky/croniter#298)."""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from _harness import main  # noqa: E402

from croniter import croniter  # noqa: E402

BASE = datetime.datetime(2026, 11, 16, 0, 0, 0)


def _next_float():
    it = croniter("*/5 * * * *", BASE)
    return lambda: it.get_next()


def _next_datetime():
    it = croniter("*/5 * * * *", BASE)
    return lambda: it.get_next(datetime.datetime)


def _prev_datetime():
    it = croniter("*/5 * * * *", BASE)
    return lambda: it.get_prev(datetime.datetime)


def _next_seconds():
    it = croniter("*/15 * * * * *", BASE)
    return lambda: it.get_next(datetime.datetime)


def builders():
    return {
        "next_5min_float": _next_float,
        "next_5min_datetime": _next_datetime,
        "prev_5min_datetime": _prev_datetime,
        "next_15sec_datetime": _next_seconds,
    }


if __name__ == "__main__":
    main(builders)
