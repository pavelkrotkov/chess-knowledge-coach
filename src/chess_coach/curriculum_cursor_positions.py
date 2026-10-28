"""Validate bounded scan positions and pending candidates."""

from .curriculum_cursor_coordinates import valid_due, valid_new
from .curriculum_cursor_phase import validate_phase, validate_scheduled
from .curriculum_cursor_values import integer, text


def validate_positions(state: dict) -> None:
    _seen(state)
    if not integer(state["scheduled_after"], 0, 2**63 - 1):
        raise ValueError("invalid scheduled position")
    validate_scheduled(state)
    if not valid_due(state["due_after"]) or not valid_new(state["new_after"], False):
        raise ValueError("invalid scan position")
    if not valid_new(state["pending"], True):
        raise ValueError("invalid pending candidate")
    if state["phase"] == "new" and state["pending"] is None and state["scheduled_after"] != 0:
        raise ValueError("orphaned scheduled scan")
    validate_phase(state)


def _seen(state: dict) -> None:
    seen = state["seen"]
    if not isinstance(seen, list) or len(seen) > state["limit"] or len(seen) != len(set(seen)):
        raise ValueError("invalid selected prompts")
    if any(not text(key, 128) for key in seen):
        raise ValueError("invalid selected prompt")
