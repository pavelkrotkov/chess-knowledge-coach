"""Read current cached skewer examples without running board proofs."""

import sqlite3
import time

from .protection_game_current import READ_SECONDS, _fresh
from .short_mate_trend_store import read
from .skewer_sample_cache import binding, location, valid


def _sample(games):
    eligible = sum(game["eligible"] for game in games)
    rows = [row for game in games for row in game["results"]]
    return {
        "games": len(games),
        "examined": len(rows),
        "pending": eligible - len(rows),
        "unresolved": sum(row[1] == "unknown" for row in rows),
        "withheld": sum(bool(game.get("source_unavailable")) for game in games),
        "examples": [
            {"position_id": row[0], "played": row[1] == "played"}
            for row in rows
            if row[1] in {"played", "other"}
        ][:20],
    }


def report(db, learner, root):
    deadline = time.monotonic() + READ_SECONDS
    path = location(db, root)
    state = read(path, binding(db, learner), validator=valid) if path else None
    if state is None:
        return None
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    try:
        state = _fresh(db, learner, state, deadline)
        if state is None:
            return None
        return {
            "newer": _sample(state["games"][:20]),
            "earlier": _sample(state["games"][20:40]),
            "selection_complete": state["selection_complete"],
            "unavailable": state["unavailable"],
            "duplicates": state["duplicates"],
        }
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return None
    finally:
        db.connection.set_progress_handler(None, 0)
