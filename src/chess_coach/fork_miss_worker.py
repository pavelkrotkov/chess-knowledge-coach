"""Resume bounded comparison work after the independent readiness scan."""

import os
import sqlite3
import time
from contextlib import suppress

from .capture_game_trend_current import frontier_matches
from .fork_game_proof import Deadline
from .fork_game_trend_paths import binding as readiness_binding
from .fork_game_trend_paths import location as readiness_location
from .fork_game_trend_validate import validate as readiness_validate
from .fork_miss_progress import advance
from .fork_miss_store import binding, location, readiness, validate
from .opening_queue_budget import BrowserBudget
from .short_mate_trend_cohort import snapshot
from .short_mate_trend_store import read, write
from .tactical_course_budget import PreviewUnavailable

CYCLE_SECONDS = 5.0
TURN_SECONDS = 0.5


def _readiness(db, learner, root):
    state = read(
        readiness_location(db, root), readiness_binding(db, learner), validator=readiness_validate
    )
    return state if state and state["selection_complete"] else None


def run(db, learner, root, *, seconds=CYCLE_SECONDS):
    path = location(db, root)
    current = _readiness(db, learner, root)
    if path is None or not current:
        return
    candidates, _, frontier, signatures = snapshot(db, learner, current["checked"])
    if not frontier_matches(current, candidates, frontier, signatures):
        return
    key = binding(db, learner)
    version = readiness(current)
    old = read(path, key, validator=validate)
    # Keep only exact matching entries when readiness advances; advance validates each one.
    state = {
        "binding": key,
        "readiness": version,
        "rows": old["rows"] if old else {},
        "rotation": old.get("rotation", 0) if old else 0,
    }
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + min(seconds, CYCLE_SECONDS))
    try:
        advance(db, learner, current, state, budget, TURN_SECONDS)
        budget.check()
    except (PreviewUnavailable, Deadline):
        if budget._version() != budget.version:
            return
    write(path, state)


def after_pipeline(db, learner, started):
    if time.monotonic() - started > 29 * 60:
        return
    with suppress(
        OSError,
        sqlite3.Error,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        PreviewUnavailable,
        Deadline,
    ):
        run(db, learner, os.environ.get("CHESS_PROJECT_ROOT"))
