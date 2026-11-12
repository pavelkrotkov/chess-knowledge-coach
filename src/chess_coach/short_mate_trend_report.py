"""Read only already-computed, current short-mate game samples."""

import sqlite3

from .capture_game_trend_current import current
from .dated_game_trend import choose
from .mate_game_trend import _comparable
from .short_mate_game_counts import add, empty, finish
from .short_mate_trend_paths import binding, location
from .short_mate_trend_store import read


def _sample(games):
    result = empty(sum(item["eligible"] for item in games))
    result["games"] = len(games)
    result["newest"] = games[0]["date"] if games else None
    result["oldest"] = games[-1]["date"] if games else None
    result["opportunity_games"] = 0
    for item in games:
        if any(row[1] in {"missed", "preserved"} for row in item["results"]):
            result["opportunity_games"] += 1
        for position_id, outcome, reason in item["results"]:
            add(result, {"position_id": position_id}, outcome, reason)
    return finish(result)


def _qualified(comparable, samples):
    if not comparable:
        return False
    return all(
        sample["complete"] and sample["opportunities"] >= 5 and sample["opportunity_games"] >= 3
        for sample in samples
    )


def _historical_links(db, state, candidates, samples, before, historical):
    # Current short-mate reports retain their established checks. The historical
    # view also verifies cached example ownership within the same read version.
    return not historical or current(db, state, candidates, samples, before)


def report(db, learner, root):
    try:
        path = location(db, root)
        state = read(path, binding(db, learner))
        if not state:
            return None
        before = db.connection.execute("PRAGMA data_version").fetchone()[0]
        selected = choose(db, learner, state, strict=False)
        if not selected:
            return None
        state, candidates, coverage, historical = selected
        games = state["games"]
        newer, earlier = _sample(games[:20]), _sample(games[20:40])
        if not _historical_links(db, state, candidates, (newer, earlier), before, historical):
            return None
        dates = [item["date"] for item in games]
        comparable = state["selection_complete"] and _comparable(
            [newer, earlier], dates, coverage, state["unavailable"]
        )
        qualified = _qualified(comparable, (newer, earlier))
        return {
            "historical": historical,
            "through": games[0]["date"] if historical else None,
            "qualified": qualified,
            "newer": newer,
            "earlier": earlier,
            "comparable": comparable,
            "coverage": coverage,
            "duplicates": state["duplicates"],
            "unavailable": state["unavailable"],
        }
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return None
