"""Present only current worker-produced fork comparisons."""

import sqlite3
import time

from .fork_miss_counts import _sample
from .fork_miss_current import _current
from .fork_miss_match import _qualified
from .fork_miss_store import binding, location, readiness, validate
from .opening_queue_budget import BrowserBudget
from .short_mate_trend_store import read
from .tactical_course_budget import PreviewUnavailable


def report(db, learner, root, state, coverage):
    try:
        cache = read(location(db, root), binding(db, learner), validator=validate)
        if not cache or cache["readiness"] != readiness(state):
            return None
        budget = BrowserBudget(db)
        budget.expires = min(budget.expires, time.monotonic() + 2.0)
        with budget.scope(snapshot=True):
            if not _current(db, learner, state, cache["rows"], budget):
                return None
            samples = [
                _sample(state["games"][:20], cache["rows"]),
                _sample(state["games"][20:40], cache["rows"]),
            ]
            qualified = _qualified(state, samples, coverage, db)
        return {"newer": samples[0], "earlier": samples[1], "qualified": qualified}
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        PreviewUnavailable,
    ):
        return None
