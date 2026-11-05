"""Validate the bounded recent-material continuation state."""

POLICY = "material-recent-v1"
WINDOW = 40


def initial(*, next_recent=False):
    return {
        "version": POLICY,
        "after": None,
        "ply": 0,
        "within": False,
        "seen": 0,
        "next_recent": next_recent,
    }


def finished(state):
    seen = state["seen"] + 1
    if seen >= WINDOW:
        return initial(next_recent=state["next_recent"])
    return {**state, "within": False, "ply": 0, "seen": seen}
