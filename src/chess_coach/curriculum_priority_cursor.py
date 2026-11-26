"""Version and validate a signed qualified-family ordering snapshot."""

from .curriculum_priority_validate import validate_priority

POLICY = "qualified-family-v1:mastery-v2-90d"
LEGACY_CAPTURE_POLICY = "qualified-family-v2:capture-practice-v1"
CAPTURE_POLICY = "qualified-family-v3:capture-files-v1"
CAPTURE_POLICIES = {LEGACY_CAPTURE_POLICY, CAPTURE_POLICY}


def upgrade(state, *, capture=False):
    if state["v"] == 6:
        policy = CAPTURE_POLICY if capture else POLICY
        state.update(v=8, priority_policy=policy, priority_goal="balanced", priority=None)
        if capture:
            state["capture_files"] = None
            state["capture_selection"] = False
    return state


def inherit(old, state):
    return (
        upgrade(state, capture=old.get("priority_policy") in CAPTURE_POLICIES)
        if old["v"] == 8
        else state
    )


def bind_goal(state, goal):
    if state["v"] == 8:
        state["priority_goal"] = goal


def validate(state):
    from .curriculum_window_scope import GOALS

    if (
        state["priority_policy"] not in {POLICY, *CAPTURE_POLICIES}
        or state["priority_goal"] not in GOALS
    ):
        raise ValueError("qualified priority policy changed")
    validate_priority(
        state["priority"], state["scan_limit"], capture=state["priority_policy"] in CAPTURE_POLICIES
    )
    # Only the new capture policy has a signed preselection file observation.
    if state["priority_policy"] == CAPTURE_POLICY:
        from .curriculum_priority_validate import _capture_input

        _capture_input(state["capture_files"])
        if type(state["capture_selection"]) is not bool:
            raise ValueError("invalid capture selection scope")
    if state["priority_policy"] in CAPTURE_POLICIES:
        _matches(state)


def _matches(state):
    if state["priority"] is not None:
        matches = state["priority"]["capture_matches"]
        if matches and (state["phase"] != "capture" or state["capture_pending"] is None):
            raise ValueError("invalid capture schedule progress")
