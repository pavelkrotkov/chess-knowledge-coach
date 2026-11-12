"""Read a bounded public continuation from the validated immutable index."""

import json
import sqlite3

from .opening_course_public_candidate import candidate
from .opening_profile_lookup import MAX_GAMES, _validate, guard
from .opening_profile_play import PARENT_PLIES


def lookup(path, parent, move, owned, *, expires=None):
    db = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        guard(db, expires)
        metadata = {
            key: json.loads(value)
            for key, value in db.execute("SELECT key,value FROM metadata LIMIT 32")
        }
        _validate(metadata)
        rows = db.execute(
            """SELECT game_id,MIN(ply) FROM moves WHERE parent=? AND uci=? AND ply<=?
            GROUP BY game_id ORDER BY game_id LIMIT ?""",
            (parent, move, PARENT_PLIES, MAX_GAMES),
        ).fetchall()
        for game_id, first in rows:
            try:
                result = candidate(db, game_id, first, parent, move, owned)
            except (ValueError, TypeError, KeyError, IndexError):
                continue
            if result is not None:
                return result
        return None
    finally:
        db.close()
