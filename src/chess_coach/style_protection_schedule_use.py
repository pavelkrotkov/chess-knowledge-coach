"""Revalidate original protection and its exact purpose request binding."""

import json

from .fact_fingerprint import canonical
from .purpose_current import owned
from .style_protection_schedule_binding import capture


def source_issue(db, learner, row):
    if row["binding_json"] is None or row["position_id"] is None:
        return "original_source_unavailable"
    item = {
        "game_id": row["game_id"],
        "position_id": row["position_id"],
        "status": "ready",
        "detail": "eligible",
    }
    try:
        actual, reason = capture(db, learner, item)
        if reason != "current":
            return reason
        return (
            None
            if canonical(actual) == canonical(json.loads(row["binding_json"]))
            else "original_source_changed"
        )
    except (TypeError, ValueError, KeyError):
        return "original_source_unavailable"


def valid_request(db, learner, row, request_id):
    try:
        request = owned(db, request_id, learner)
        return request["game_id"] == row["game_id"] and request["position_id"] == row["position_id"]
    except (TypeError, ValueError, KeyError):
        return False
