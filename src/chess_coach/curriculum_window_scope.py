"""Validate the explicit optional curriculum goal and wall-clock window."""

from datetime import UTC, datetime, timedelta

from .mastery_time import parse_utc

POLICY = "curriculum-goal-window-v1"
GOALS = {"balanced": None, "capture": 0, "fork": 1, "mate": 2, "promotion": 3}
MAX_MINUTES = 180


def clock():
    return datetime.now(UTC)


def options(goal, minutes):
    if goal is None:
        goal = "balanced"
    if not isinstance(goal, str) or goal not in GOALS:
        raise ValueError("unsupported practice goal")
    if minutes is not None and (type(minutes) is not int or not 1 <= minutes <= MAX_MINUTES):
        raise ValueError("window minutes must be 1..180")
    return goal, minutes


def create(state, goal, minutes, page_limit, *, reset_turn=True):
    goal, minutes = options(goal, minutes)
    issued = clock()
    turn = GOALS[goal]
    if reset_turn and turn is not None:
        state["family_turn"] = turn
    return {
        "v": 7,
        "policy": POLICY,
        "goal": goal,
        "minutes": minutes,
        "page_limit": page_limit,
        "issued_at": issued.isoformat(),
        "expires_at": (issued + timedelta(minutes=minutes)).isoformat() if minutes else None,
        "state": state,
        "new_seen": [],
        "repeat_due": [],
        "source_refreshed": False,
    }


def expired(value):
    deadline = parse_utc(value["expires_at"])
    return deadline is not None and clock() >= deadline
