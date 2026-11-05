"""Resolve one immutable assessment and its currentness."""

import json

from .mate_assessment_events import replay
from .mate_assessment_scope import scope
from .unified_source_current import require_current


def item(db, row, corpus):
    if row["source_type"] != "corpus" or row["objective"] != "mate_within_two":
        return None
    binding = json.loads(row["provenance_json"]).get("related_mate")
    if not isinstance(binding, dict) or not isinstance(binding.get("assessment"), dict):
        return None
    assessment = binding["assessment"]
    current = row["source_version"] == corpus
    try:
        require_current(db, row)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        current = False
    try:
        observed = replay(db, row)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        observed = {"outcome": "unavailable", "hints": None, "reveals": None, "illegal": None}
    return {
        "attempt_id": row["attempt_id"],
        "started_at": row["started_at"],
        "current": current,
        "scope": scope(row, binding, assessment),
        **observed,
    }
