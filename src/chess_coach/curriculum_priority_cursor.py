"""Version and validate a signed qualified-family ordering snapshot."""

from .curriculum_priority_validate import validate_priority

POLICY = "qualified-family-v1:mastery-v2-90d"
CAPTURE_POLICY = "qualified-family-v2:capture-practice-v1"


def upgrade(state, *, capture=False):
    if state["v"] == 6:
        policy = CAPTURE_POLICY if capture else POLICY
        state.update(v=8, priority_policy=policy, priority_goal="balanced", priority=None)
    return state


def inherit(old, state):
    return (
        upgrade(state, capture=old.get("priority_policy") == CAPTURE_POLICY)
        if old["v"] == 8
        else state
    )


def bind_goal(state, goal):
    if state["v"] == 8:
        state["priority_goal"] = goal


def validate(state):
    from .curriculum_window_scope import GOALS

    if (
        state["priority_policy"] not in {POLICY, CAPTURE_POLICY}
        or state["priority_goal"] not in GOALS
    ):
        raise ValueError("qualified priority policy changed")
    validate_priority(
        state["priority"], state["scan_limit"], capture=state["priority_policy"] == CAPTURE_POLICY
    )
