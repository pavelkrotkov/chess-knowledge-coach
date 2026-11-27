"""Validate the strict common-choice continuation."""

from .curriculum_cursor_values import common as common_values
from .curriculum_priority_cursor import COMMON_POLICY
from .curriculum_priority_validate import _capture_input


def common_as_of(state):
    return state["as_of"] if state.get("priority_policy") == COMMON_POLICY else None


def validate(state):
    _capture_input(state["common_input"])
    common = state["common"]
    if common is None:
        return
    if not isinstance(common, dict) or set(common) != {"binding", "matches", "complete", "winner"}:
        raise ValueError("invalid common continuation")
    common_values(common)


def bind(state, binding):
    common = state["common"]
    if common is None:
        common = {"binding": binding, "matches": 0, "complete": False, "winner": None}
        state["common"] = common
    if common["binding"] != binding:
        raise ValueError("common sources changed; restart the plan")
    return common


def finish(state):
    state["common"]["complete"] = True
    state["scheduled_after"] = 0


def bind_input(state, actual):
    if state["common_input"] is None:
        state["common_input"] = actual
    elif state["common_input"] != actual:
        raise ValueError("common practice changed; restart the plan")
