"""Recheck one first-encounter fork assessment and its event history."""

from .fork_history_result import details
from .mate_assessment_events import replay
from .unified_source_current import require_current


def item(db, row, corpus, check, *, cache=None):
    entry = {"attempt_id": row["attempt_id"], "started_at": row["started_at"]}
    try:
        observed = replay(db, row)
        entry.update(hints=observed["hints"], reveals=observed["reveals"])
        if row["source_version"] != corpus:
            return {**entry, "status": "stale"}
        if row["status"] == "active":
            require_current(db, row, related_check=check, related_cache=cache)
            return {**entry, "status": "incomplete"}
        status, answered_at = details(db, row, check=check, cache=cache)
        return {**entry, "status": status, "answered_at": answered_at}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return {**entry, "status": "stale"}
