"""Versioned deterministic order for bounded new-item families."""

from .curriculum_cursor_capture import _digest
from .curriculum_cursor_values import integer

# The signed turn fixes this order for all pages of one plan.
FAMILIES = ("capture", "fork", "new")


def current_family(state):
    index = state["family_index"]
    if state["v"] in {6, 8}:
        from .curriculum_mix_order import family

        return family(state)
    if state["v"] == 5:
        if index < 3:
            return ("capture", "fork", "public")[(state["family_turn"] + index) % 3]
        return "public" if index == 3 and state["public_status"] == "deferred" else "new"
    return FAMILIES[(state["family_turn"] + index) % 3] if index < 3 else "new"


def validate_families(state):
    end = {5: 4, 6: 8, 8: 8}.get(state["v"], 3)
    turn = 3 if state["v"] in {6, 8} else 2
    if not integer(state["family_turn"], 0, turn) or not integer(state["family_index"], 0, end):
        raise ValueError("invalid family continuation")
    _validate_positions(state)
    _validate_fork(state)


def _validate_positions(state):
    if state["phase"] == "due" and (state["new_after"] is not None or state["pending"] is not None):
        raise ValueError("due scan cannot contain corpus position")
    if (
        state["phase"] in {"capture", "fork", "public", "canonical"}
        and state["pending"] is not None
    ):
        raise ValueError("owned scan cannot contain pending corpus candidate")


def _validate_fork(state):
    pending = state["fork_pending"]
    if pending is not None and (not _digest(pending) or state["phase"] != "fork"):
        raise ValueError("invalid fork binding")
    _validate_order(state, pending)


def _validate_order(state, pending):
    if state["phase"] == "fork" and pending is None and state["scheduled_after"]:
        raise ValueError("orphaned fork scan")
    if state["phase"] != "due" and state["phase"] != current_family(state):
        raise ValueError("invalid family phase")
