"""Replay exact public first-turn branches for early central-capture availability."""

import json
import sqlite3

from .opening_fit_reference_counts import MAX_GAMES, summarize
from .opening_profile_lookup import _validate, guard
from .opening_profile_store import TRANSFORM
from .style_early_center import MAX_PLY


def _rows(db, parent, move, ply):
    return db.execute(
        """SELECT g.id,g.total_plies,g.context FROM moves m JOIN games g ON g.id=m.game_id
        WHERE m.parent=? AND m.uci=? AND m.ply=? ORDER BY g.id LIMIT ?""",
        (parent, move, ply, MAX_GAMES + 1),
    ).fetchall()


def sample(path, parent, move, color, control, deadline, *, decision_ply=None, transform=TRANSFORM):
    db = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        guard(db, deadline)
        metadata = {
            k: json.loads(v) for k, v in db.execute("SELECT key,value FROM metadata LIMIT 32")
        }
        _validate(metadata, transform=transform)
        ply = decision_ply if decision_ply is not None else (1 if color == "white" else 2)
        if not 1 <= ply <= MAX_PLY or (ply % 2 == 1) != (color == "white"):
            raise ValueError("opening decision ply unavailable")
        rows = _rows(db, parent, move, ply)
        decision = {"parent": parent, "move": move, "ply": ply} if decision_ply else None
        return summarize(db, rows, color, control, deadline, decision)
    finally:
        db.close()
