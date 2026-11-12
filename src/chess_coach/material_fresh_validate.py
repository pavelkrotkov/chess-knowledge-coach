"""Validate the bounded private cursor for the fresh material lane."""

from .deep_selection_source import MAX_DECISIONS

LIMIT = 10


def _position(item):
    return (
        isinstance(item, list)
        and len(item) == 2
        and type(item[0]) is int
        and 0 < item[0] < 2**63
        and type(item[1]) is int
        and 0 <= item[1] <= MAX_DECISIONS
    )


def _positions(values):
    if not isinstance(values, list) or len(values) > LIMIT:
        return False
    if not all(_position(item) for item in values):
        return False
    return len({item[0] for item in values}) == len(values)


def valid(state):
    return (
        isinstance(state, dict)
        and type(state.get("version")) is int
        and state["version"] == 2
        and type(state.get("next_fresh")) is bool
        and type(state.get("last")) is int
        and 0 <= state["last"] < 2**63
        and _positions(state.get("positions"))
    )
