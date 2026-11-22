"""Advance a bounded public-mate keyset and its scheduled conflict check."""

import sqlite3

from .curriculum_public_candidate import attempt, resume
from .curriculum_public_source import rows
from .public_mate_contract import OBJECTIVE
from .tactical_course_budget import PreviewUnavailable


def scan(db, state, subject, counts, check):
    if db.compat32:
        state["public_status"] = "learning_unavailable"
        return [], "learning_unavailable", None, None
    if check is None:
        state["public_status"] = "unavailable"
        return [], "unavailable", None, None
    # A bound conflict must finish before later public rows are considered.
    if state["public_pending"] is not None:
        return resume(db, state, subject, counts, check)
    # Count every examined row, including objectives this policy cannot use.
    remaining = max(0, state["scan_limit"] - counts.get("public_examined", 0))
    batch = rows(db, state["public_after"] or [0, ""], remaining)
    for row in batch[:remaining]:
        check()
        result = _row(db, state, subject, counts, check, row)
        if result is not None:
            return result
    return _finish(state, len(batch) > remaining)


def _finish(state, more):
    if more:
        state["public_status"] = "deferred"
        return [], "deferred", "public_scan_incomplete", None
    if state["public_status"] not in {"provided", "exposure_unknown", "unavailable"}:
        state["public_status"] = "exhausted" if state["public_examined"] else "unavailable"
    return [], state["public_status"], None, None


def _row(db, state, subject, counts, check, row):
    prior = state["public_after"]
    state["public_after"] = [row["id"], row["task_id"]]
    state["public_examined"] += 1
    counts["public_examined"] = counts.get("public_examined", 0) + 1
    if row["objective"] != OBJECTIVE:
        return None
    try:
        result = attempt(db, state, subject, counts, check, row["version"], row["task_id"])
        return result if result is not None and (result[0] or result[2]) else None
    except (PreviewUnavailable, sqlite3.OperationalError):
        # Never skip a row interrupted before a conflict binding was recorded.
        if state["public_pending"] is None:
            state["public_after"] = prior
            state["public_examined"] -= 1
            counts["public_examined"] -= 1
        raise
