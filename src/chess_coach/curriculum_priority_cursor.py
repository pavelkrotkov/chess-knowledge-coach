"""Version and validate a signed qualified-family ordering snapshot."""

from .curriculum_priority_validate import validate_priority

POLICY = "qualified-family-v1:mastery-v2-90d"


def upgrade(state):
    if state["v"] == 6:
        state.update(v=8, priority_policy=POLICY, priority_goal="balanced", priority=None)
    return state


def inherit(old, state):
    return upgrade(state) if old["v"] == 8 else state


def bind_goal(state, goal):
    if state["v"] == 8:
        state["priority_goal"] = goal


def validate(state):
    from .curriculum_window_scope import GOALS

    if state["priority_policy"] != POLICY or state["priority_goal"] not in GOALS:
        raise ValueError("qualified priority policy changed")
    validate_priority(state["priority"], state["scan_limit"])
