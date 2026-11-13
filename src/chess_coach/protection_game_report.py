"""Summarize current, independently proved protection observations."""

import sqlite3

from .capture_game_counts import add, empty, finish
from .capture_game_trend_bounds import bounds
from .mate_game_comparability import reason as comparability_reason
from .protection_game_current import current

# Reuse the existing rate bounds with protection-specific outcome names.
CHOICES = {"protected": "played", "missed": "other"}


def _sample(games):
    result = empty(sum(game["eligible"] for game in games))
    result.update(
        games=len(games),
        newest=games[0]["date"] if games else None,
        oldest=games[-1]["date"] if games else None,
        resolved_games=0,
        available_games=0,
        withheld_games=0,
        withheld_turns=0,
    )
    for game in games:
        result["available_games"] += bool(game["results"])
        result["withheld_games"] += bool(game.get("source_unavailable"))
        result["withheld_turns"] += game.get("unavailable_checked", 0)
        result["resolved_games"] += any(row[1] in CHOICES for row in game["results"])
        for position_id, outcome, reason in game["results"]:
            add(result, {"position_id": position_id}, CHOICES.get(outcome, outcome), reason)
    return finish(result)


def report(db, learner, root):
    try:
        state = current(db, learner, root)
        if state is None:
            return None
        games = state["games"]
        newer, earlier = _sample(games[:20]), _sample(games[20:40])
        if not state["selection_complete"]:
            reason = "selection_pending"
        elif newer["withheld_games"] or earlier["withheld_games"]:
            reason = "source_unavailable"
        else:
            reason = comparability_reason(
                (newer, earlier),
                [game["date"] for game in games],
                state["coverage"],
                state["unavailable"],
            )
        return {
            "newer": newer,
            "earlier": earlier,
            "comparable_reason": reason,
            "bounds": bounds(reason is None, earlier, newer),
            "coverage": state["coverage"],
            "duplicates": state["duplicates"],
            "unavailable": state["unavailable"],
        }
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return None
