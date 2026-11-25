"""Prepare and explain one signed family priority within the existing scan."""

from .curriculum_mix_order import family
from .curriculum_priority import explain, snapshot, unknown


def prepare_priority(db, state, learner, budget, check):
    if state["v"] != 8 or state["priority"] is not None:
        return
    state["priority"] = snapshot(db, learner, state, check) if budget is not None else unknown()
    state["phase"] = family(state)


def annotate(state, phase, items):
    if state["v"] != 8 or state["priority"] is None or phase not in {"capture", "fork"}:
        return
    for item in items:
        item["reason"] += " " + explain(state, phase)
