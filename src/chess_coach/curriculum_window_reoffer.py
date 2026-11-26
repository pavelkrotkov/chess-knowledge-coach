"""Prove which signed window offers have not become scheduled."""

import sqlite3
import time

from .curriculum_cursor import revision
from .curriculum_window_reoffer_scan import scan
from .tactical_course_budget import SLICE_SECONDS, PreviewUnavailable


def unstarted(db, value, budget):
    wanted = set(value["new_seen"])
    if not wanted:
        return set()
    if budget is None:
        raise ValueError("previous offers could not be rechecked")
    budget.expires = min(budget.expires, time.monotonic() + SLICE_SECONDS)
    try:
        with budget.scope(snapshot=False):
            return scan(db, value["state"], wanted, budget)
    except (
        PreviewUnavailable,
        sqlite3.Error,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
    ):
        raise ValueError("previous offers could not be rechecked") from None


def history(db, value, budget, *, force_changed=False):
    old = value["state"]
    changed = force_changed or old["revision"] != revision(db)
    released = unstarted(db, value, budget) if changed else set()
    seen = [key for key in old["seen"] if key not in released]
    new_seen = [key for key in value["new_seen"] if key not in released]
    return changed, seen, new_seen
