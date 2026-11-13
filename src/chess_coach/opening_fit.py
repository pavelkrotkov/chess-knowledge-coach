"""Attach optional bounded center-choice learning fit to opening options."""

import sqlite3
import time
from contextlib import contextmanager

from .opening_fit_owned import collect
from .opening_fit_rank import rank
from .opening_fit_reference import sample
from .style_schedule_budget import BudgetExceeded
from .style_schedule_clock import DEADLINE
from .tactical_course_budget import PreviewUnavailable

RESERVE = 2.0


@contextmanager
def _owned_scope(db, budget):
    budget.check()
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= budget.expires), 1000)
    token = DEADLINE.set(budget.expires)
    try:
        yield
        budget.check()
    finally:
        DEADLINE.reset(token)
        db.connection.set_progress_handler(None, 0)


def _public(path, items, color, control, budget):
    result = {}
    for item in items:
        budget.check()
        selection = item["selection"]
        result[item["uci"]] = sample(
            path, selection["parent"], item["uci"], color, control, budget.expires
        )
    return result


def assess(db, learner, guard, budget, items, black_parent):
    original = budget.expires
    budget.expires = original - RESERVE
    result = {"status": "deferred", "colors": {}}
    try:
        with _owned_scope(db, budget):
            owned = collect(db, learner, black_parent)
        result = {"status": owned["status"], "owned": owned, "colors": {}}
        for color in ("white", "black"):
            own = owned.get("colors", {}).get(color, {})
            public = _public(
                guard[1], items[color], color, own.get("time_control", "unknown"), budget
            )
            result["colors"][color] = {
                "owned": own,
                "public": public,
                "recommended": None,
            }
        for color in ("white", "black"):
            values = result["colors"][color]
            values["recommended"] = rank(items[color], values["public"], values["owned"])
    except (
        PreviewUnavailable,
        BudgetExceeded,
        TimeoutError,
        OSError,
        sqlite3.Error,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
    ):
        result["status"] = "deferred"
    finally:
        budget.expires = original
    budget.check()
    return result
