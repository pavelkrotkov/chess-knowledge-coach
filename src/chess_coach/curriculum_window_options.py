"""Validate the learner goal and requested wall-clock window."""

GOALS = {"balanced": None, "capture": 0, "fork": 1, "mate": 2, "promotion": 3}
MAX_MINUTES = 180


def options(goal, minutes):
    if goal is None:
        goal = "balanced"
    if not isinstance(goal, str) or goal not in GOALS:
        raise ValueError("unsupported practice goal")
    if minutes is not None and (type(minutes) is not int or not 1 <= minutes <= MAX_MINUTES):
        raise ValueError("window minutes must be 1..180")
    return goal, minutes
