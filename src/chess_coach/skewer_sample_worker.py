"""Resume bounded royal-skewer checks after ordinary processing."""

import os
import sqlite3
import time
from contextlib import suppress

from .skewer_sample_cache import location
from .skewer_sample_scan import run as advance

CYCLE_SECONDS = 10.0


def run(db, learner, root, *, seconds=CYCLE_SECONDS):
    path = location(db, root)
    if path is None:
        return
    deadline = time.monotonic() + min(seconds, CYCLE_SECONDS)
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    try:
        advance(db, learner, path, deadline)
    finally:
        db.connection.set_progress_handler(None, 0)


def after_pipeline(db, learner, started):
    if time.monotonic() - started > 29 * 60:
        return
    with suppress(OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        run(db, learner, os.environ.get("CHESS_PROJECT_ROOT"))
