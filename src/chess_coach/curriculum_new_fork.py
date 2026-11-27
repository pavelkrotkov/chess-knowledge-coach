"""Bound one exact fork candidate and its scheduled conflict scan."""

import sqlite3

from .curriculum_capture_conflict import check_conflicts
from .curriculum_fork_source import read
from .tactical_course_budget import PreviewUnavailable


def _candidate(db, state, subject, counts, check):
    from .curriculum_common_cursor import common_as_of

    candidate, status, report = read(
        db, subject, state["corpus_version"], check, as_of=common_as_of(state)
    )
    pending = state["fork_pending"]
    if pending is not None and (candidate is None or candidate["binding"] != pending):
        raise ValueError("fork source changed; restart the plan")
    if candidate is None:
        return [], status, None, report
    if candidate["prompt_key"] in state["seen"]:
        return [], "duplicate", None, report
    return check_conflicts(db, state, counts, check, candidate, report, pending_key="fork_pending")


def scan(db, state, learner, counts, check):
    if db.compat32:
        return [], "learning_unavailable", None, None
    if check is None:
        return [], "unavailable", None, None
    working, work_counts = dict(state), dict(counts)
    try:
        result = _candidate(db, working, learner, work_counts, check)
    except PreviewUnavailable:
        state["fork_pending"] = working["fork_pending"]
        return [], "deferred", "fork_scan_incomplete", None
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        state["fork_pending"] = working["fork_pending"]
        check()
        if state["fork_pending"] is not None:
            raise ValueError("fork source changed; restart the plan") from None
        return [], "unavailable", None, None
    state.update(working)
    counts.update(work_counts)
    return result
