"""Bounded source-checked owned capture admission after due reviews."""

import sqlite3
import time

from .curriculum_capture_candidate import check_candidate
from .tactical_course_budget import SLICE_SECONDS, PreviewUnavailable


def scan(db, state, subject, scan, budget):
    if db.compat32:
        state["phase"] = "new"
        return [], "learning_unavailable", None, None
    if budget is None:
        if state["capture_pending"] is not None:
            return [], "deferred", "capture_scan_incomplete", None
        state["phase"] = "new"
        return [], "unavailable", None, None
    expires = time.monotonic() + SLICE_SECONDS

    def check():
        if time.monotonic() >= expires:
            raise PreviewUnavailable("request deadline reached")

    working, work_scan = dict(state), dict(scan)
    try:
        with budget.scope(snapshot=False):
            result = check_candidate(db, working, subject, work_scan, check)
        state.update(working)
        scan.update(work_scan)
        return result
    except PreviewUnavailable:
        return [], "deferred", "capture_scan_incomplete", None
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        if state["capture_pending"] is not None:
            raise ValueError("capture source changed; restart the plan") from None
        if working["capture_pending"] is not None:
            state["capture_pending"] = working["capture_pending"]
            return [], "deferred", "capture_scan_incomplete", None
        state["phase"] = "new"
        return [], "unavailable", None, None
