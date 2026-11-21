"""Check consistency between continuation scan phases."""

from .curriculum_cursor_capture import validate_capture, validate_order
from .curriculum_cursor_values import integer


def validate_phase(state: dict) -> None:
    if len(state["seen"]) >= state["limit"]:
        raise ValueError("completed plans cannot continue")
    if state["phase"] in {"due", "capture"} and (
        state["new_after"] is not None or state["pending"] is not None
    ):
        raise ValueError("pre-corpus scan cannot contain a corpus position")
    if state["v"] == 2:
        validate_capture(state)
    pending, prior = state["pending"], state["new_after"]
    validate_order(pending, prior)


def validate_scheduled(state: dict) -> None:
    if not integer(state["scheduled_best"], 0, 2**63 - 1):
        raise ValueError("invalid scheduled winner")
    if state["phase"] in {"capture", "new"} and state["scheduled_best"] != 0:
        raise ValueError("invalid scheduled winner")


def after_due(state):
    return "capture" if state["v"] == 2 else "new"
