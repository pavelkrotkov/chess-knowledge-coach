"""Read bounded cached protection coverage without rerunning board proofs."""

import sqlite3
import time

from .capture_game_trend_validate import matches_frontier
from .protection_game_cache import binding, location, valid
from .protection_game_review import binding as review_binding
from .protection_game_source import binding as analysis_binding
from .short_mate_trend_cohort import snapshot
from .short_mate_trend_store import read

READ_SECONDS = 2.0


def _positions(db, item):
    # Membership also protects decision links when a cache has been altered.
    expected = {row[0] for row in item["results"]}
    if not expected:
        return True
    placeholders = ",".join("?" for _ in expected)
    rows = db.connection.execute(
        f"SELECT id FROM positions WHERE game_id=? AND id IN ({placeholders})",
        (item["id"], *expected),
    ).fetchall()
    return {row[0] for row in rows} == expected


def _game(db, learner, item):
    try:
        return (
            _positions(db, item)
            and analysis_binding(db, item["id"]) == item["analysis"]
            and review_binding(db, item["id"], learner)[0] == item["review"]
        )
    except (ValueError, TypeError, KeyError, IndexError):
        return False


def _withhold(item):
    # Stale rows are unchecked, not negative or unresolved opportunities.
    item["unavailable_checked"] = len(item["results"])
    item["results"] = []
    item["source_unavailable"] = True


def _recheck(db, learner, games, deadline):
    for item in games:
        if time.monotonic() >= deadline:
            return False
        if item["results"] and not _game(db, learner, item):
            _withhold(item)
    return time.monotonic() < deadline


def _fresh(db, learner, state, deadline):
    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    games, coverage, frontier, signatures = snapshot(
        db, learner, state["checked"], seconds=min(1.0, max(0.0, deadline - time.monotonic()))
    )
    if (frontier, signatures) != (state["frontier"], state["checked"]):
        return None
    if not matches_frontier(state, games):
        return None
    state["coverage"] = coverage
    # A prior cohort needs its own current-source audit before it can be used.
    state.pop("prior", None)
    if not _recheck(db, learner, state["games"][:40], deadline):
        return None
    return state if db.connection.execute("PRAGMA data_version").fetchone()[0] == before else None


def current(db, learner, root):
    deadline = time.monotonic() + READ_SECONDS
    path = location(db, root)
    state = read(path, binding(db, learner), validator=valid) if path else None
    if state is None:
        return None
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    try:
        return _fresh(db, learner, state, deadline)
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return None
    finally:
        db.connection.set_progress_handler(None, 0)
