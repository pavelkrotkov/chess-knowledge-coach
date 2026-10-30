"""Check allocation identity and diagnostic currentness before proof work."""

from .style_protection_schedule_status_fields import _slot_bound
from .style_purpose_view import current_view

STATES = {
    "ready": "pending",
    "pending": "pending",
    "running": "running",
    "interrupted": "interrupted",
    "insufficient": "insufficient",
    "stale": "stale",
}


def admit(db, learner, slot, snapshot, state):
    if slot["status"] != "complete":
        return STATES.get(slot["status"], "unknown"), None
    if not _slot_bound(db, slot, slot["request_id"]):
        return "unknown", None
    issue, view = current_view(db, learner, slot, snapshot, state["views"])
    return (None, view) if issue == "current" else (issue, None)
