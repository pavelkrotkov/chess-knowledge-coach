"""Resume a small private knight-fork scan after normal worker duties."""

import os
import sqlite3
import time
from contextlib import suppress

from .capture_game_trend_scan import _advance, _resume
from .fork_game_proof import classify
from .fork_game_trend_paths import TURN_SECONDS, binding, location
from .fork_game_trend_validate import validate
from .short_mate_trend_cohort import snapshot
from .short_mate_trend_select import initial
from .short_mate_trend_store import read, write

CYCLE_SECONDS = 5.0


def run(db, learner, root, *, seconds=CYCLE_SECONDS):
    path = location(db, root)
    if path is None:
        return
    deadline = time.monotonic() + min(seconds, CYCLE_SECONDS)
    key = binding(db, learner)
    old = read(path, key, validator=validate)
    games, coverage, frontier, signatures = snapshot(db, learner, old["checked"] if old else ())
    state = _resume(old, key, frontier, signatures, games)
    state["coverage"] = coverage
    try:
        _advance(
            db, learner, games, state, deadline, classifier=classify, turn_seconds=TURN_SECONDS
        )
    except (ValueError, TypeError, IndexError):
        state = initial(key, frontier, None)
        state["coverage"] = coverage
    write(path, state)


def after_pipeline(db, learner, started):
    if time.monotonic() - started > 29 * 60:
        return
    with suppress(OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        run(db, learner, os.environ.get("CHESS_PROJECT_ROOT"))
