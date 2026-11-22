"""Advance the exact canonical task list and bound scheduled conflicts."""

import sqlite3

from .curriculum_canonical_candidate import attempt
from .curriculum_canonical_context import context
from .curriculum_canonical_source import choices
from .tactical_course_budget import PreviewUnavailable


def _context(db, state, subject, check):
    try:
        current = context(db, subject, state["scan_limit"], check)
    except (ValueError, TypeError, KeyError, IndexError):
        check()
        if state["canonical_pending"] is not None or state["canonical_scope"] is not None:
            raise ValueError("canonical context changed; restart the plan") from None
        state["canonical_status"] = "unavailable"
        return None
    if state["canonical_scope"] is not None and state["canonical_scope"] != current["scope"]:
        raise ValueError("canonical context changed; restart the plan")
    state["canonical_context"] = current["state"]
    state["canonical_scope"] = current["scope"]
    if current["scope"] is None:
        state["canonical_status"] = "unavailable"
        return None
    return current


def scan(db, state, subject, counts, check):
    if db.compat32:
        state["canonical_status"] = "learning_unavailable"
        return [], "learning_unavailable", None, None
    if check is None:
        state["canonical_status"] = "unavailable"
        return [], "unavailable", None, None
    # Recheck recorded practice rather than trusting a prior page's relevance.
    current = _context(db, state, subject, check)
    if current is None:
        return [], state["canonical_status"], None, None
    options = choices(current["done"])
    # A pending task must resume its scheduled conflict before later tasks.
    if state["canonical_pending"] is not None:
        index = state["canonical_after"] - 1
        if index < 0 or index >= len(options):
            raise ValueError("canonical source changed; restart the plan")
        return attempt(db, state, subject, counts, check, options[index], current)
    # Public and canonical candidates consume one shared page allowance.
    used = counts.get("public_examined", 0) + counts.get("canonical_examined", 0)
    remaining = max(0, state["scan_limit"] - used)
    return _rows(db, state, subject, counts, check, current, options, remaining)


def _rows(db, state, subject, counts, check, current, options, remaining):
    for index in range(
        state["canonical_after"], min(len(options), state["canonical_after"] + remaining)
    ):
        check()
        result = _row(db, state, subject, counts, check, options[index], current, index)
        if result is not None:
            return result
    if state["canonical_after"] < len(options):
        state["canonical_status"] = "deferred"
        return [], "deferred", "canonical_scan_incomplete", None
    if state["canonical_status"] not in {"provided", "exposure_unknown", "unavailable"}:
        state["canonical_status"] = "exhausted"
    return [], state["canonical_status"], None, None


def _row(db, state, subject, counts, check, choice, current, index):
    prior = (state["canonical_after"], state["canonical_examined"])
    state["canonical_after"] = index + 1
    state["canonical_examined"] += 1
    counts["canonical_examined"] = counts.get("canonical_examined", 0) + 1
    counts["_canonical_before"] = prior
    try:
        result = attempt(db, state, subject, counts, check, choice, current)
        return result if result is not None and (result[0] or result[2]) else None
    except (PreviewUnavailable, sqlite3.OperationalError):
        # An interrupted unbound task must remain the next task inspected.
        if state["canonical_pending"] is None:
            state["canonical_after"], state["canonical_examined"] = prior
            counts["canonical_examined"] -= 1
        raise
