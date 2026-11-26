"""Prepare and explain one signed family priority within the existing scan."""

from .curriculum_mix_order import family
from .curriculum_priority import explain, snapshot, unknown
from .curriculum_priority_cursor import CAPTURE_POLICY


def prepare_priority(db, state, learner, budget, check):
    if state["v"] != 8 or state["priority"] is not None:
        return
    priority = snapshot(db, learner, state, check) if budget is not None else unknown()
    if state["priority_policy"] == CAPTURE_POLICY:
        from .curriculum_capture_inputs import current

        priority["capture_input"] = current(db, learner, budget.project_root, check)
        priority["capture_sources"] = None
    state["priority"] = priority
    state["phase"] = family(state)


def annotate(state, phase, items):
    if state["v"] != 8 or state["priority"] is None or phase not in {"capture", "fork"}:
        return
    for item in items:
        item["reason"] += " " + explain(state, phase)
