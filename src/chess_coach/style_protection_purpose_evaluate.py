"""Evaluate current original proof and exact diagnostic once per decision."""

from .style_protection_purpose_merge import merge
from .style_protection_purpose_observation import observation
from .style_protection_schedule_status_fields import _slot_bound, provenance
from .style_purpose_view import current_view


def evaluate(db, learner, slot, context, snapshot, state, ordinary, budget, history):
    issue, view = _admit(db, learner, slot, snapshot, state)
    if issue:
        state["counts"][f"protection_{issue}"] += 1
        return
    result, item, source_current = observation(
        db, learner, context, slot, snapshot, view, budget, history
    )
    state["counts"][f"protection_{result}"] += 1
    if source_current:
        state["protection_checks"][slot["id"]] = {
            **provenance(slot),
            "purpose_state": "current",
            "comparison_state": result,
        }
    else:
        state["protection_checks"][slot["id"]] = {"state": "unknown", "detail": result}
    if item is None:
        return
    key = (slot["game_id"], slot["position_id"])
    state["protection_seen"].add(key)
    merge(key, item, ordinary, state)


def _admit(db, learner, slot, snapshot, state):
    key = (slot["game_id"], slot["position_id"])
    if slot["request_id"] in state["protection_requests"] or key in state["protection_seen"]:
        return "duplicate", None
    state["protection_requests"].add(slot["request_id"])
    if slot["status"] != "complete" or not _slot_bound(db, slot, slot["request_id"]):
        return "unknown", None
    issue, view = current_view(db, learner, slot, snapshot, state["views"])
    return (None, view) if issue == "current" else (issue, None)
