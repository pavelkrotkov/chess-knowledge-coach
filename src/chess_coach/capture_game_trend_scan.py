"""Advance a separate bounded capture scan after ordinary worker duties."""

import sqlite3
import time
from contextlib import suppress
from functools import partial

from .capture_game_proof import classify
from .capture_game_root_budget import fit
from .capture_game_root_detail import inspect as inspect_roots
from .capture_game_root_validate import discard_invalid
from .capture_game_trend_paths import TURN_SECONDS, binding, location
from .capture_game_trend_validate import matches_frontier, validate
from .short_mate_trend_cohort import snapshot
from .short_mate_trend_scan import _inspect
from .short_mate_trend_select import initial, select
from .short_mate_trend_store import read, write
from .short_mate_trend_turns import inspect

# The earlier short-mate scan retains its own budget and runs before this one.
CYCLE_SECONDS = 10.0


def _advance(
    db,
    learner,
    games,
    state,
    deadline,
    *,
    classifier=None,
    turn_seconds=TURN_SECONDS,
    inspector=None,
    retain_fields=(),
):
    fields = retain_fields
    if inspector is None:
        inspector = partial(inspect, classifier=classifier, seconds=turn_seconds)
    if classifier is None:
        discard_invalid(state)
        fields = ("root_details", "root_refresh")
        inspector = partial(inspect_roots, state=state, classifier=classify, seconds=turn_seconds)
    select(db, learner, games, state, deadline, retain_fields=fields)
    consumed = {str(row[0]) for row in state["checked"]}
    state["retained"] = {
        key: item for key, item in state["retained"].items() if key not in consumed
    }
    if state["selection_complete"]:
        _inspect(
            db,
            learner,
            state,
            deadline,
            inspector=inspector,
            turn_seconds=turn_seconds,
            recheck_complete=classifier is None,
        )


def _resume(old, key, frontier, signatures, games):
    if old and old["frontier"] == frontier and signatures == old["checked"]:
        return old if matches_frontier(old, games) else initial(key, frontier, None)
    return initial(key, frontier, old)


def run(db, learner, root, *, seconds=CYCLE_SECONDS):
    path = location(db, root)
    if path is None:
        return
    deadline = time.monotonic() + min(seconds, CYCLE_SECONDS)
    from .capture_certificate_worker import run as certify

    with suppress(TimeoutError):
        certify(db, learner, root, min(deadline, time.monotonic() + CYCLE_SECONDS / 2))
    key = binding(db, learner)
    old = read(path, key, validator=validate)
    games, coverage, frontier, signatures = snapshot(db, learner, old["checked"] if old else ())
    state = _resume(old, key, frontier, signatures, games)
    state["coverage"] = coverage
    try:
        _advance(db, learner, games, state, deadline)
    except (ValueError, TypeError, IndexError):
        state = initial(key, frontier, None)
        state["coverage"] = coverage
    fit(state)
    write(path, state)


def after_pipeline(db, learner, started):
    if time.monotonic() - started > 29 * 60:
        return
    with suppress(OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        run(db, learner, db.capture_root)
