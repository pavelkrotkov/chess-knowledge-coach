"""Read only current, worker-computed knight-fork game samples."""

import sqlite3

from .capture_game_trend_current import current, frontier_matches
from .fork_game_counts import add, empty, finish
from .fork_game_trend_paths import binding, location
from .fork_game_trend_validate import validate
from .short_mate_trend_cohort import snapshot
from .short_mate_trend_store import read


def _sample(games):
    result = empty(sum(item["eligible"] for item in games))
    result["games"] = len(games)
    result["newest"] = games[0]["date"] if games else None
    result["oldest"] = games[-1]["date"] if games else None
    for game in games:
        for position, outcome, reason in game["results"]:
            add(result, position, outcome, reason)
    return finish(result)


def report(db, learner, root):
    try:
        state = read(location(db, root), binding(db, learner), validator=validate)
        if not state:
            return None
        before = db.connection.execute("PRAGMA data_version").fetchone()[0]
        candidates, coverage, frontier, signatures = snapshot(db, learner, state["checked"])
        if not frontier_matches(state, candidates, frontier, signatures):
            return None
        games = state["games"]
        newer, earlier = _sample(games[:20]), _sample(games[20:40])
        if not current(db, state, candidates, (newer, earlier), before):
            return None
        return {
            "newer": newer,
            "earlier": earlier,
            "coverage": coverage,
            "selection_complete": state["selection_complete"],
            "duplicates": state["duplicates"],
            "unavailable": state["unavailable"],
        }
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return None
