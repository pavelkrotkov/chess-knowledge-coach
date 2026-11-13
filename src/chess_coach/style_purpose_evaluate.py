"""Revalidate scheduled purpose results and enforce one decision vote."""

from .style_center_coverage import collect as collect_center
from .style_center_coverage import overlap as center_overlap
from .style_early_center_report import collect as collect_early
from .style_early_center_report import note as note_early
from .style_purpose_choice import observation
from .style_purpose_view import current_view


# Targeted root choices and ordinary conditional controls are separate cohorts.
def evaluate(db, learner, slot, context, snapshot, state, seen):
    kind = slot["kind"]
    source_state, view = current_view(db, learner, slot, snapshot, state["views"])
    if source_state != "current":
        state["counts"][f"{kind}_{source_state}"] += 1
        note_early(state, slot, _early_reason(source_state))
        return
    key = (slot["game_id"], slot["position_id"])
    if key in seen:
        state["counts"][f"{kind}_duplicate"] += 1
        if not slot.get("early_center_target"):
            center_overlap(kind, snapshot, state)
        note_early(state, slot, "ordinary_overlap")
        return
    result, item = observation(db, context, slot, snapshot, view)
    state["counts"][f"{kind}_{result}"] += 1
    if not slot.get("early_center_target"):
        collect_center(db, context, slot, snapshot, view, state, key, result)
    if result == "outside_check":
        collect_early(context, slot, snapshot, view, state)
    else:
        note_early(state, slot, "unsupported")
    if item is not None:
        seen.add(key)
        state["observations"].append(item)


def _early_reason(source_state):
    if source_state == "stale":
        return "stale"
    return "unsupported" if source_state in {"unknown", "insufficient"} else "unchecked"
