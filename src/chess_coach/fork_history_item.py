"""Recheck one first-encounter fork assessment and its event history."""

from .fork_history_result import result
from .mate_assessment_events import replay
from .unified_source_current import require_current


def item(db, row, corpus, check):
    entry = {"attempt_id": row["attempt_id"], "started_at": row["started_at"]}
    try:
        observed = replay(db, row)
        entry.update(hints=observed["hints"], reveals=observed["reveals"])
        if row["source_version"] != corpus:
            return {**entry, "status": "stale"}
        if row["status"] == "active":
            require_current(db, row, related_check=check)
            status = "incomplete"
        else:
            status = result(db, row, check=check)
        return {**entry, "status": status}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return {**entry, "status": "stale"}
