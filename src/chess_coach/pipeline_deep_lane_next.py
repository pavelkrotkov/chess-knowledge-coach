"""Prepare one archive sweep and advance unfinished deep games."""

from collections import deque

from .pipeline_deep_cursor import scan
from .pipeline_deep_cursor_state import _cursor
from .pipeline_deep_recent import next_game


def archive_sweep(db, config, report, state, lane):
    if lane != "archive":
        return None
    limit = config.deep_max_scan - report["examined"]
    pending = state["archive"]
    if pending:
        key, _, version = _cursor(db, config)
        games = db.connection.execute(
            "SELECT id FROM games WHERE id>? ORDER BY id LIMIT ?",
            (pending["id"], limit),
        ).fetchall()
        remaining = limit - 1
    else:
        key, version, games = scan(db, config, limit=limit)
        remaining = limit
    return {
        "key": key,
        "version": version,
        "games": deque(games),
        "more": len(games) > remaining,
    }


def candidate(db, config, state, lane, archive):
    if lane == "archive":
        item = state[lane]
        if item is None and archive["games"]:
            row = archive["games"].popleft()
            item = {"id": row["id"], "started": None, "attempts": 0}
        return item, state, bool(archive["games"]) or archive["more"]
    if state[lane] is not None:
        return state[lane], state, state["after"] is not None
    return next_game(db, config, state)
