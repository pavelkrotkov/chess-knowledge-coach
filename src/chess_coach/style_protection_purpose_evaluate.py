"""Evaluate current original proof and exact diagnostic once per decision."""

from .style_protection_purpose_admission import admit as _admit
from .style_protection_purpose_merge import merge
from .style_protection_purpose_observation import observation
from .style_protection_schedule_status_fields import provenance


def evaluate(db, learner, slot, context, snapshot, state, ordinary, budget, history):
    issue, view = _admit(db, learner, slot, snapshot, state)
    if issue:
        state["counts"][f"protection_{issue}"] += 1
        return
    key = (slot["game_id"], slot["position_id"])
    duplicate = (
        slot["request_id"] in state["protection_requests"] or key in state["protection_seen"]
    )
    result, item, source_current = observation(
        db,
        learner,
        context,
        slot,
        snapshot,
        view,
        budget,
        history,
        state["protection_sources"],
        duplicate,
    )
    state["counts"][f"protection_{result}"] += 1
    if source_current:
        state["protection_requests"].add(slot["request_id"])
        state["protection_checks"][slot["id"]] = {
            **provenance(slot),
            "purpose_state": "current",
            "comparison_state": result,
        }
    else:
        state["protection_checks"][slot["id"]] = {"state": "unknown", "detail": result}
    if item is None:
        return
    state["protection_seen"].add(key)
    merge(key, item, ordinary, state)
