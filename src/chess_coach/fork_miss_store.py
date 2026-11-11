"""Bind a separate comparison cache to the readiness policy and cohort."""

from .fact_fingerprint import canonical, digest
from .fork_game_trend_paths import binding as readiness_binding
from .fork_game_trend_paths import location as readiness_location
from .fork_miss_verify import VERSION


def location(db, root):
    path = readiness_location(db, root)
    return (
        path.with_name(path.name.replace(".knight-fork-trend.json", ".knight-fork-miss.json"))
        if path
        else None
    )


def binding(db, learner):
    return digest(canonical([VERSION, readiness_binding(db, learner)]))


# Retention requires the same independent game, source signature, and turn outcome.
def identity(game, row):
    return digest(canonical([game["id"], game["signature"], game["identity"], row]))


def readiness(state):
    return digest(
        canonical(
            [
                state["frontier"],
                state["checked"],
                state["games"],
                state["selection_complete"],
                state["coverage"],
                state["duplicates"],
                state["unavailable"],
            ]
        )
    )


def _entry(key, row):
    if (
        not isinstance(key, str)
        or not key.isdecimal()
        or not isinstance(row, list)
        or len(row) != 5
    ):
        return False
    return all(
        (
            type(row[0]) is int,
            row[0] > 0,
            isinstance(row[1], str),
            row[2] in {"played", "miss", "unresolved", "retry"},
            row[3] is None or isinstance(row[3], str),
            isinstance(row[4], str),
            row[2] not in {"played", "miss"} or isinstance(row[3], str),
        )
    )


def _rotation(value):
    return type(value) is int and value >= 0


def _envelope(data, expected):
    return isinstance(data, dict) and data.get("binding") == expected


def validate(data, expected):
    if not _envelope(data, expected):
        return False
    rows = data.get("rows")
    if not isinstance(rows, dict) or not isinstance(data.get("readiness"), str):
        return False
    return all(
        (
            len(rows) <= 40000,
            _rotation(data.get("rotation", 0)),
            all(_entry(key, row) for key, row in rows.items()),
        )
    )
