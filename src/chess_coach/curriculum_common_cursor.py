"""Validate the strict untimed common-choice continuation."""

from .curriculum_cursor_values import hex_digest, integer


def validate(state):
    if not hex_digest(state["common_input"]):
        raise ValueError("invalid common input")
    common = state["common"]
    if common is None:
        return
    if not isinstance(common, dict) or set(common) != {"binding", "matches", "complete", "winner"}:
        raise ValueError("invalid common continuation")
    _validate_common(common)


def _validate_common(common):
    if not hex_digest(common["binding"]) or not integer(common["matches"], 0, 7):
        raise ValueError("invalid common continuation")
    if type(common["complete"]) is not bool or common["winner"] not in {None, "capture", "fork"}:
        raise ValueError("invalid common continuation")
    if common["winner"] is not None and not common["complete"]:
        raise ValueError("invalid common continuation")


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
