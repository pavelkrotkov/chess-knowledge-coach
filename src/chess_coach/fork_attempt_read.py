"""Replay a bounded fork-attempt page under the caller's request budget."""

from .fork_attempt_rows import PAGE
from .fork_history_item import item
from .related_fork_assessment_scope import is_source
from .tactical_course_budget import PreviewUnavailable


def _entry(db, row, corpus, budget, cache):
    basic = {
        "attempt_id": row["attempt_id"],
        "started_at": row["started_at"],
        "source_version": row["source_version"],
        "older": row["source_version"] != corpus,
    }
    try:
        if not is_source(row):
            return None
        return basic | item(db, row, row["source_version"], budget.check, cache=cache)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return basic | {"status": "stale"}


def read(db, selected, corpus, budget):
    output, last, cache, incomplete = [], None, {}, False
    for row in selected[:PAGE]:
        try:
            with budget.scope(snapshot=False):
                entry = _entry(db, row, corpus, budget, cache)
        except PreviewUnavailable:
            entry = {
                "attempt_id": row["attempt_id"],
                "started_at": row["started_at"],
                "source_version": row["source_version"],
                "older": row["source_version"] != corpus,
                "status": "unavailable",
            }
            incomplete = True
        last = row
        if entry is not None:
            output.append(entry)
        if incomplete:
            break
    return output, last, incomplete
