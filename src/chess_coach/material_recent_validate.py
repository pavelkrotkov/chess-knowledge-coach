"""Validate the private recent-material continuation before using it."""

from .deep_selection_source import MAX_DECISIONS
from .material_recent_state import POLICY, WINDOW
from .pipeline_recent_position import position


def _position_fields(state):
    after, ply = state.get("after"), state.get("ply")
    within = state.get("within")
    return (
        position(after)
        and type(ply) is int
        and 0 <= ply <= MAX_DECISIONS
        and (not within or after is not None)
        and (within or ply == 0)
    )


def valid(state):
    if not isinstance(state, dict) or state.get("version") != POLICY:
        return False
    seen = state.get("seen")
    if type(seen) is not int or not 0 <= seen < WINDOW:
        return False
    if type(state.get("within")) is not bool or type(state.get("next_recent")) is not bool:
        return False
    return _position_fields(state)
