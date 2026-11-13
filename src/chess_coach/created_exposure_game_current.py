"""Read the current created-exposure profile and its cached independent games."""

import sqlite3
import time
from functools import partial

from .created_exposure_game_cache import binding, location, valid
from .created_exposure_game_profile import current as profile_current
from .created_exposure_game_selection import without_source
from .protection_game_current import READ_SECONDS, _fresh
from .short_mate_trend_store import read


def current(db, learner, root):
    deadline = time.monotonic() + READ_SECONDS
    path = location(db, root)
    state = read(path, binding(db, learner), validator=valid) if path else None
    if state is None:
        return None
    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    try:
        profile = state["profile"]
        if not profile_current(db, learner, profile):
            return None
        result = _fresh(
            db, learner, state, deadline, filter_games=partial(without_source, profile=profile)
        )
        if time.monotonic() >= deadline:
            return None
        return (
            result if db.connection.execute("PRAGMA data_version").fetchone()[0] == before else None
        )
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, StopIteration):
        return None
    finally:
        db.connection.set_progress_handler(None, 0)
