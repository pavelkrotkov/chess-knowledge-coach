"""Validate and rotate the bounded recent-candidate continuation."""

from .pipeline_recent_position import position

POLICY = "recent-ordinary-analysis-turn-v2"
WINDOW = 40


def initial():
    return {"version": POLICY, "after": None, "seen": 0}


def valid(state):
    if not isinstance(state, dict) or state.get("version") != POLICY:
        return False
    seen = state.get("seen")
    after = state.get("after")
    return (
        type(seen) is int
        and 0 <= seen < WINDOW
        and (seen == 0) == (after is None)
        and position(after)
    )


def next_state(state, last, examined, available, *, full):
    seen = state["seen"] + examined
    if full or not last or examined == available or seen >= WINDOW:
        return initial()
    return {"version": POLICY, "after": last, "seen": seen}
