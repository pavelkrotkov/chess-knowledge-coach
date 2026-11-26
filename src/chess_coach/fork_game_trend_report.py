"""Read only current, worker-computed knight-fork game samples."""

import sqlite3

from .capture_game_trend_current import current
from .capture_game_trend_report import _comparison
from .dated_game_trend import boundary_id, choose
from .fork_game_root_current import samples
from .fork_game_trend_paths import binding, location
from .fork_game_trend_validate import validate
from .fork_miss_report import report as miss_report
from .opening_study_source import fingerprint
from .short_mate_trend_store import read


def _selected(db, learner, path, check, as_of):
    state = read(path, binding(db, learner), validator=validate)
    if state is None:
        return None
    return choose(db, learner, state, check=check, as_of=as_of)


def report(db, learner, root, *, check=None, as_of=None):
    try:
        path = location(db, root)
        before_file = fingerprint([path]) if path is not None else None
        before = db.connection.execute("PRAGMA data_version").fetchone()[0]
        selected = _selected(db, learner, path, check, as_of)
        if not selected:
            return None
        state, candidates, coverage, historical = selected
        games = state["games"]
        newer, earlier = samples(db, learner, games, check)
        comparison = (
            None if historical else miss_report(db, learner, root, state, coverage, check=check)
        )
        reason = _comparison(
            state, games, candidates, (newer, earlier), coverage, check or (lambda: None)
        )
        if not current(
            db, state, candidates, (newer, earlier), before, artifact=(path, before_file)
        ):
            return None
        return {
            "historical": historical,
            "boundary": len(games) > 40,
            "boundary_id": boundary_id(games),
            "comparable": reason is None,
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
