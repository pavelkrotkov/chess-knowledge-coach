"""Recheck every stored comparison against its game and analysis."""

from .fork_miss_source import marker
from .fork_miss_store import identity


def _positions(state):
    return {
        str(position): (game["id"], identity(game, row), outcome)
        for game in state["games"][:40]
        for row in game["results"]
        for position, outcome, _ in [row]
        if outcome in {"played", "awaiting"}
    }


def _linked(expected, key, row):
    if key not in expected or (row[0], row[4]) != expected[key][:2]:
        return False
    outcome = expected[key][2]
    return row[2] not in {"played", "miss"} or ((row[2] == "played") == (outcome == "played"))


def _current(db, learner, state, rows, budget):
    expected = _positions(state)
    if any(not _linked(expected, key, row) for key, row in rows.items()):
        return False
    for key, row in rows.items():
        budget.check()
        if marker(db, row[0], int(key), learner) != row[1]:
            return False
    return True
