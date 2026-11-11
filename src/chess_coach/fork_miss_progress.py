"""Resume comparison entries fairly across dated samples."""

import time

from .fork_miss_entry import _entry
from .fork_miss_source import marker
from .fork_miss_store import identity


def _entries(current):
    return [
        (game["id"], position, outcome, identity(game, row))
        for game in current["games"][:40]
        for row in game["results"]
        for position, outcome, _ in [row]
        if outcome in {"played", "awaiting"}
    ]


def _retain(state, entries):
    wanted = {str(position): (game, signature) for game, position, _, signature in entries}
    state["rows"] = {
        key: row
        for key, row in state["rows"].items()
        if key in wanted and (row[0], row[4]) == wanted[key]
    }


def _step(db, learner, state, budget, turn_seconds, entry):
    game, position, outcome, signature = entry
    with budget.scope(snapshot=True):
        current_marker = marker(db, game, position, learner)
        old = state["rows"].get(str(position))
        if old and old[1] == current_marker and old[2] != "retry":
            return None
        deadline = min(time.monotonic() + turn_seconds, budget.expires)
        result = [*_entry(db, learner, game, position, outcome, deadline), signature]
    return str(position), result


def advance(db, learner, current, state, budget, turn_seconds):
    entries = _entries(current)
    _retain(state, entries)
    if not entries:
        return
    # Advancing over cached entries prevents a long prefix from starving later games.
    start = state.get("rotation", 0) % len(entries)
    for offset in range(len(entries)):
        if time.monotonic() + turn_seconds >= budget.expires:
            break
        state["rotation"] = (start + offset + 1) % len(entries)
        result = _step(
            db, learner, state, budget, turn_seconds, entries[(start + offset) % len(entries)]
        )
        if result is not None:
            key, row = result
            state["rows"][key] = row
