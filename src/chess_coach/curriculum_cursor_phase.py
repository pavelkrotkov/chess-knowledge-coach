"""Check consistency between continuation scan phases."""

from .curriculum_cursor_values import integer


def validate_phase(state: dict) -> None:
    if len(state["seen"]) >= state["limit"]:
        raise ValueError("completed plans cannot continue")
    if state["phase"] == "due" and (state["new_after"] is not None or state["pending"] is not None):
        raise ValueError("due scan cannot contain a corpus position")
    pending, prior = state["pending"], state["new_after"]
    if pending is not None and prior is not None and pending[:2] <= prior:
        raise ValueError("pending candidate does not follow the corpus position")


def validate_scheduled(state: dict) -> None:
    if not integer(state["scheduled_best"], 0, 2**63 - 1):
        raise ValueError("invalid scheduled winner")
    if state["phase"] == "new" and state["scheduled_best"] != 0:
        raise ValueError("invalid scheduled winner")
