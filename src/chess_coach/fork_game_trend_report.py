"""Read only current, worker-computed knight-fork game samples."""

import sqlite3

from .capture_game_trend_current import current
from .dated_game_trend import choose
from .fork_game_counts import add, empty, finish
from .fork_game_trend_paths import binding, location
from .fork_game_trend_validate import validate
from .fork_miss_report import report as miss_report
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
        selected = choose(db, learner, state)
        if not selected:
            return None
        state, candidates, coverage, historical = selected
        games = state["games"]
        newer, earlier = _sample(games[:20]), _sample(games[20:40])
        comparison = None if historical else miss_report(db, learner, root, state, coverage)
        if not current(db, state, candidates, (newer, earlier), before):
            return None
        return {
            "historical": historical,
            "through": games[0]["date"] if historical else None,
            "newer": newer,
            "earlier": earlier,
            "comparison": comparison,
            "coverage": coverage,
            "selection_complete": state["selection_complete"],
            "duplicates": state["duplicates"],
            "unavailable": state["unavailable"],
        }
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return None
