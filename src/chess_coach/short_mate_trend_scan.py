"""Resume a small amount of independent game inspection after worker duties."""

import os
import sqlite3
import time
from contextlib import suppress

from .short_mate_trend_cohort import snapshot
from .short_mate_trend_paths import binding, location
from .short_mate_trend_select import initial, select
from .short_mate_trend_store import read, write
from .short_mate_trend_turns import TURN_SECONDS, inspect

CYCLE_SECONDS = 20.0
TURN_LIMIT = 40


def _next(cursor, size):
    if size != 40:
        return (cursor + 1) % size
    # Alternate older and newer cohorts so arrivals cannot starve either sample.
    return cursor + 20 if cursor < 20 else (cursor - 19) % 20


def _inspect(db, learner, state, deadline, *, inspector=None, turn_seconds=None):
    if inspector is None:
        inspector = inspect
    if turn_seconds is None:
        turn_seconds = TURN_SECONDS
    games = state["games"][:40]
    if not games:
        return
    used = visited = 0
    cursor = state.get("rotation", 0) % len(games)
    while used < TURN_LIMIT and visited < len(games):
        # Never start a local proof when the cycle cannot supply its full budget.
        if time.monotonic() + turn_seconds >= deadline:
            break
        item = games[cursor]
        if len(item["results"]) < item["eligible"]:
            used += inspector(db, learner, item, deadline, min(4, TURN_LIMIT - used))
        cursor = _next(cursor, len(games))
        visited += 1
    state["rotation"] = cursor


def run(db, learner, root, *, seconds=CYCLE_SECONDS):
    path = location(db, root)
    if path is None:
        return
    deadline = time.monotonic() + min(seconds, CYCLE_SECONDS)
    key = binding(db, learner)
    old = read(path, key)
    games, coverage, frontier, signatures = snapshot(db, learner, old["checked"] if old else ())
    # The report and worker use the same short snapshot to reject stale inputs.
    if old and old["frontier"] == frontier and signatures == old["checked"]:
        state = old
    else:
        state = initial(key, frontier, old)
    state["coverage"] = coverage
    select(db, learner, games, state, deadline)
    if state["selection_complete"]:
        _inspect(db, learner, state, deadline)
    write(path, state)


def after_pipeline(db, learner, started):
    # Leave time for the service to finish and persist normal worker health.
    if time.monotonic() - started > 29 * 60:
        return
    with suppress(OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        run(db, learner, os.environ.get("CHESS_PROJECT_ROOT"))
