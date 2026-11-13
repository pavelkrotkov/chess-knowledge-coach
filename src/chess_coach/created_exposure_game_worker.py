"""Maintain a bounded, separate created-exposure game sample."""

import os
import sqlite3
import time
from contextlib import suppress
from functools import partial

from .created_exposure_game_cache import location
from .created_exposure_game_profile import current
from .created_exposure_game_sample import TURN_SECONDS
from .created_exposure_game_selection import selection
from .created_exposure_game_turns import inspect
from .protection_game_worker import _guarded
from .short_mate_trend_scan import _inspect
from .short_mate_trend_store import write

CYCLE_SECONDS = 20.0


def _scan(db, learner, state, deadline):
    if not state["selection_complete"]:
        return
    inspector = partial(_guarded, inspector=partial(inspect, profile=state["profile"]))
    _inspect(
        db,
        learner,
        state,
        deadline,
        inspector=inspector,
        turn_seconds=TURN_SECONDS,
        recheck_complete=True,
    )


def run(db, learner, root, *, seconds=CYCLE_SECONDS):
    path = location(db, root)
    if path is None:
        return
    deadline = time.monotonic() + min(seconds, CYCLE_SECONDS)
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    try:
        state = selection(db, learner, path, deadline)
        if state is None:
            return
        _scan(db, learner, state, deadline)
        # A source change during the scan must not bless the stored results.
        if not current(db, learner, state["profile"]):
            raise ValueError("profile changed")
        write(path, state)
    finally:
        db.connection.set_progress_handler(None, 0)


def after_pipeline(db, learner, started):
    if time.monotonic() - started > 29 * 60:
        return
    with suppress(OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        run(db, learner, os.environ.get("CHESS_PROJECT_ROOT"))
