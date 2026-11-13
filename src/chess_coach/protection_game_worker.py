"""Maintain one bounded private cache of independent protection game coverage."""

import os
import sqlite3
import time
from contextlib import suppress

from .capture_game_trend_scan import _resume
from .protection_game_cache import binding, location, valid
from .protection_game_source import prepare
from .protection_game_turns import TURN_SECONDS, inspect
from .short_mate_trend_cohort import snapshot
from .short_mate_trend_scan import _inspect
from .short_mate_trend_select import select
from .short_mate_trend_store import read, write

CYCLE_SECONDS = 20.0


def _guarded(db, learner, item, deadline, quota):
    # Keep the last checkpoint if the deadline interrupts an inspection.
    candidate = {**item, "results": list(item["results"])}
    try:
        consumed = inspect(db, learner, candidate, deadline, quota)
    except (ValueError, TypeError, KeyError, IndexError, sqlite3.Error):
        if time.monotonic() >= deadline:
            return 1
        item["analysis"] = None
        item["review"] = None
        item["results"] = []
        return 1
    item.update(candidate)
    return consumed


def run(db, learner, root, *, seconds=CYCLE_SECONDS):
    path = location(db, root)
    if path is None:
        return
    deadline = time.monotonic() + min(seconds, CYCLE_SECONDS)
    # Bound indexed lineage queries as well as the cooperative board proofs.
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    try:
        _run(db, learner, path, deadline)
    finally:
        db.connection.set_progress_handler(None, 0)


def _run(db, learner, path, deadline):
    key = binding(db, learner)
    old = read(path, key, validator=valid)
    games, coverage, frontier, signatures = snapshot(db, learner, old["checked"] if old else ())
    state = _resume(old, key, frontier, signatures, games)
    state["coverage"] = coverage
    select(
        db,
        learner,
        games,
        state,
        deadline,
        retain_fields=("analysis", "review"),
        prepare_game=prepare,
    )
    if state["selection_complete"]:
        _inspect(
            db,
            learner,
            state,
            deadline,
            inspector=_guarded,
            turn_seconds=TURN_SECONDS,
            recheck_complete=True,
        )
    write(path, state)


def after_pipeline(db, learner, started):
    if time.monotonic() - started > 29 * 60:
        return
    with suppress(OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        run(db, learner, os.environ.get("CHESS_PROJECT_ROOT"))
