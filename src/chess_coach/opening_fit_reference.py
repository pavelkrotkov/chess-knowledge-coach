"""Replay exact public first-turn branches for early central-capture availability."""

import json
import sqlite3

from .opening_fit_replay import inspect
from .opening_profile_lookup import _validate, guard
from .style_early_center import MAX_PLY

MAX_GAMES = 10


def _rows(db, parent, move, ply):
    return db.execute(
        """SELECT g.id,g.total_plies,g.context FROM moves m JOIN games g ON g.id=m.game_id
        WHERE m.parent=? AND m.uci=? AND m.ply=? ORDER BY g.id LIMIT ?""",
        (parent, move, ply, MAX_GAMES + 1),
    ).fetchall()


# Stored broadcast metadata currently lacks time control; unknown stays unknown.
def _game(db, game, color, control, deadline):
    identity, total, metadata = game
    context = json.loads(metadata)
    public_control = context.get("TimeControl")
    if public_control not in (None, "", "?") and public_control != control:
        return "context", False
    if total < MAX_PLY:
        return "short", False
    rows = db.execute(
        "SELECT ply,parent,uci,san FROM moves WHERE game_id=? AND ply<=? ORDER BY ply",
        (identity, MAX_PLY),
    ).fetchall()
    return inspect(rows, color, deadline)


def sample(path, parent, move, color, control, deadline):
    db = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        guard(db, deadline)
        metadata = {
            k: json.loads(v) for k, v in db.execute("SELECT key,value FROM metadata LIMIT 32")
        }
        _validate(metadata)
        rows = _rows(db, parent, move, 1 if color == "white" else 2)
        counts = {"valid": 0, "available": 0, "short": 0, "inconsistent": 0, "context": 0}
        for game in rows[:MAX_GAMES]:
            try:
                state, available = _game(db, game, color, control, deadline)
            except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                state, available = "inconsistent", False
            counts[state] += 1
            counts["available"] += available
        return {**counts, "sampled": min(len(rows), MAX_GAMES), "more": len(rows) > MAX_GAMES}
    finally:
        db.close()
