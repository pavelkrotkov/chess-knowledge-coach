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
