"""Validate one first-encounter capture assessment and its current source."""

import json

from .capture_plan_result import result
from .mate_assessment_events import replay
from .related_capture_assessment_context import VERSION
from .unified_source_current import require_current


def _rating(row):
    binding = json.loads(row["provenance_json"])["related_capture"]
    context = binding["assessment"].get("context")
    if not isinstance(context, dict) or context.get("version") != VERSION:
        return None
    rating = context.get("content_rating")
    return rating // 200 * 200 if type(rating) is int and 0 <= rating < 4000 else None


def item(db, row, corpus, cache, check):
    entry = {"attempt_id": row["attempt_id"], "started_at": row["started_at"], "rating": None}
    try:
        if row["source_version"] != corpus:
            return {**entry, "status": "stale"}
        observed = replay(db, row)
        if row["status"] == "active":
            require_current(db, row, related_cache=cache, related_check=check)
            state = {"status": "incomplete"}
        else:
            state = result(db, row, observed, related_cache=cache, related_check=check)
        entry["rating"] = _rating(row)
        return {**entry, **state, "hints": observed["hints"], "reveals": observed["reveals"]}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return {**entry, "status": "stale"}
