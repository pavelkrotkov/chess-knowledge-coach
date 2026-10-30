"""Revalidate scheduled purpose results and enforce one decision vote."""

from .style_purpose_choice import observation
from .style_purpose_view import current_view


def evaluate(db, learner, slot, context, snapshot, state, seen):
    kind = slot["kind"]
    source_state, view = current_view(db, learner, slot, snapshot, state["views"])
    if source_state != "current":
        state["counts"][f"{kind}_{source_state}"] += 1
        return
    key = (slot["game_id"], slot["position_id"])
    if key in seen:
        state["counts"][f"{kind}_duplicate"] += 1
        return
    result, item = observation(db, context, slot, snapshot, view)
    state["counts"][f"{kind}_{result}"] += 1
    if item is not None:
        seen.add(key)
        state["observations"].append(item)
