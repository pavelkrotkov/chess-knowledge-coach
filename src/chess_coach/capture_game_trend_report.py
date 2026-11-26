"""Report only current, already-computed capture choice samples."""

import sqlite3

from .capture_game_counts import add, empty, finish
from .capture_game_root_current import project
from .capture_game_trend_bounds import bounds
from .capture_game_trend_current import current
from .capture_game_trend_paths import binding, location
from .capture_game_trend_validate import validate
from .dated_game_controls import reason as control_reason
from .dated_game_trend import choose
from .mate_game_comparability import reason as comparability_reason
from .opening_study_source import fingerprint
from .short_mate_trend_report import _qualified
from .short_mate_trend_store import read


def _sample(games):
    result = empty(sum(item["eligible"] for item in games))
    result.update(
        games=len(games),
        newest=games[0]["date"] if games else None,
        oldest=games[-1]["date"] if games else None,
        opportunity_games=0,
        resolved_games=0,
    )
    for item in games:
        outcomes = {row[1] for row in item["results"]}
        result["opportunity_games"] += bool(
            outcomes & {"played", "other", "opportunity_unresolved"}
        )
        result["resolved_games"] += bool(outcomes & {"played", "other"})
        for position_id, outcome, reason in item["results"]:
            add(result, {"position_id": position_id}, outcome, reason)
    return finish(result)


def report(db, learner, root, *, check=None, as_of=None):
    try:
        path = location(db, root)
        before_file = fingerprint([path]) if path is not None else None
        state = read(path, binding(db, learner), validator=validate)
        if not state:
            return None
        # Recheck every examined source, including duplicate and unavailable rows.
        before = db.connection.execute("PRAGMA data_version").fetchone()[0]
        selected = choose(db, learner, state, check=check, as_of=as_of)
        if not selected:
            return None
        state, candidates, coverage, historical = selected
        games = state["games"]
        newer, earlier = _sample(games[:20]), _sample(games[20:40])
        project(db, learner, games[:40], (newer, earlier), check=check)
        if check is None:

            def check():
                return None

        reason = _comparison(state, games, candidates, (newer, earlier), coverage, check)
        if not current(
            db, state, candidates, (newer, earlier), before, artifact=(path, before_file)
        ):
            return None
        check()
        comparable = reason is None
        return {
            "historical": historical,
            "through": games[0]["date"] if historical else None,
            "qualified": _qualified(comparable, (newer, earlier)),
            "boundary": len(games) > 40,
            "bounds": bounds(comparable, earlier, newer),
            "newer": newer,
            "earlier": earlier,
            "comparable": comparable,
            "comparable_reason": reason,
            "coverage": coverage,
            "duplicates": state["duplicates"],
            "unavailable": state["unavailable"],
        }
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return None


def _comparison(state, games, candidates, samples, coverage, check):
    if not state["selection_complete"]:
        return "selection_pending"
    dates = [item["date"] for item in games]
    return comparability_reason(samples, dates, coverage, state["unavailable"]) or control_reason(
        games, candidates, check=check
    )
