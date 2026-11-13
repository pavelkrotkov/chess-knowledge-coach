"""Validate bounded restart state for the automatic deep lanes."""

from .pipeline_recent_position import position

WINDOW = 10
RETRIES = 2


def _pending(value, recent):
    if value is None:
        return True
    if not isinstance(value, dict):
        return False
    game, tries = value.get("id"), value.get("attempts")
    if type(game) is not int or not 0 < game < 2**63:
        return False
    if type(tries) is not int or not 0 <= tries <= RETRIES:
        return False
    return position([value.get("started"), game]) if recent else value.get("started") is None


def valid(state):
    if not isinstance(state, dict) or state.get("version") != 1:
        return False
    after = state.get("after")
    return all(
        (
            type(state.get("next_recent")) is bool,
            "archive" in state,
            "recent" in state,
            position(after),
            _pending(state.get("archive"), False),
            _pending(state.get("recent"), True),
        )
    )
