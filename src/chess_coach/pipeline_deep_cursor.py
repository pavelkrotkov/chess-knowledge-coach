"""Rotate the bounded automatic-deep archive scan."""

from .pipeline_cursor import save_cursor
from .pipeline_deep_cursor_state import _cursor


def scan(db, config, *, limit=None):
    key, cursor, recorded = _cursor(db, config)
    limit = config.deep_max_scan if limit is None else limit
    rows = db.connection.execute(
        "SELECT id FROM games WHERE id>? ORDER BY id LIMIT ?", (cursor, limit + 1)
    ).fetchall()
    if not rows and cursor:
        rows = db.connection.execute(
            "SELECT id FROM games ORDER BY id LIMIT ?", (limit + 1,)
        ).fetchall()
    return key, recorded, rows


def advance(db, key, version, game_id):
    save_cursor(db, key, game_id, version)


def retire(db, state, lane, item, archive):
    if lane == "archive":
        advance(db, archive["key"], archive["version"], item["id"])
    return {**state, lane: None}
