"""Confirm the slot and current comparison identify the same ready result."""

from .opening_explore_alternatives import describe
from .opening_explore_latest import hint


def result(db, root, learner, slot, decision, states):
    choice = decision["catalog"]["items"][0]
    state = states.get(choice["uci"], {})
    if state.get("_identity") != slot["id"] or hint(db, root, learner) != slot:
        return None
    result = describe(decision, states)[0]
    return result if result.get("ready") else None
