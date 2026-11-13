"""Validate stored mover and reply WDL bounds."""


def valid_reply(bounds, goal):
    return (
        type(goal) is int
        and goal in {0, 1}
        and isinstance(bounds, list)
        and len(bounds) == 2
        and all(type(value) is int for value in bounds)
        and -1 <= bounds[0] <= bounds[1] <= -goal
    )


def correct_root(result):
    low, high, goal = result.get("lower"), result.get("upper"), result.get("goal")
    return (
        type(low) is int
        and type(high) is int
        and type(goal) is int
        and goal in {0, 1}
        and -1 <= low <= high <= 1
        and low >= goal
    )


def result_interval(result, data, objective):
    goal, low, high = result.get("goal"), result.get("lower"), result.get("upper")
    if any(type(value) is not int for value in (goal, low, high)):
        raise ValueError("pawn result interval unavailable")
    if not (
        goal in {0, 1}
        and -1 <= low <= high <= 1
        and goal == data.get("result_goal")
        and objective == ("preserve_pawn_win" if goal == 1 else "preserve_pawn_draw")
    ):
        raise ValueError("pawn result interval unavailable")
    return goal, low, high
