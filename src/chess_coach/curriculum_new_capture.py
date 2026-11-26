"""Bounded source-checked owned capture admission after due reviews."""

import sqlite3
import time
from contextlib import nullcontext

from .curriculum_capture_candidate import check_candidate
from .tactical_course_budget import SLICE_SECONDS, PreviewUnavailable


def scan(db, state, subject, scan, budget, *, shared_check=None):
    if db.compat32:
        state["phase"] = "new"
        return [], "learning_unavailable", None, None
    if budget is None:
        if state["capture_pending"] is not None:
            return [], "deferred", "capture_scan_incomplete", None
        state["phase"] = "new"
        return [], "unavailable", None, None
    expires = time.monotonic() + SLICE_SECONDS

    def local_check():
        if time.monotonic() >= expires:
            raise PreviewUnavailable("request deadline reached")

    check = shared_check or local_check

    # Preserve the signed scan state unless a complete check can be committed.
    working, work_scan = _working(state, scan)
    try:
        with nullcontext() if shared_check else budget.scope(snapshot=False):
            result = check_candidate(db, working, subject, work_scan, check)
        state.update(working)
        scan.update(work_scan)
        return result
    except PreviewUnavailable:
        return _deferred(state, working, shared_check)
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return _failed(state, working, shared_check)


def _deferred(state, working, check):
    if check is not None and working["capture_pending"] is not None:
        state["capture_pending"] = working["capture_pending"]
    return [], "deferred", "capture_scan_incomplete", None


def _failed(state, working, check):
    prior = state["capture_pending"]
    if check is not None and working["capture_pending"] is not None:
        state["capture_pending"] = working["capture_pending"]
    if check is not None:
        check()
    if prior is not None:
        raise ValueError("capture source changed; restart the plan") from None
    if working["capture_pending"] is not None:
        state["capture_pending"] = working["capture_pending"]
        return [], "deferred", "capture_scan_incomplete", None
    state["phase"] = "new"
    return [], "unavailable", None, None


def _working(state, scan):
    working = dict(state)
    if state.get("priority") is not None:
        working["priority"] = dict(state["priority"])
    return working, dict(scan)
