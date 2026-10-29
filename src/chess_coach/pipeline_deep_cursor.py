"""Rotate a separate bounded automatic-deep scan across worker invocations."""

import json

from .deep_selection_source import learner_key
from .fact_fingerprint import canonical, digest
from .pipeline_cursor import save_cursor
from .pipeline_deep_config import public_limits
from .pipeline_inputs import fingerprint


def scan(db, config):
    key = digest("automatic-deep-cursor-v1:" + learner_key(config.learner))
    version = fingerprint({"policy": "automatic-deep-v1", "per_game": config.deep_per_game})
    recorded = canonical({"version": version, "limits": public_limits(config)})
    row = db.connection.execute(
        "SELECT last_game_id,scan_hash FROM pipeline_cursors WHERE account_key=?", (key,)
    ).fetchone()
    previous = _record(row[1]) if row else {}
    cursor = row[0] if row and previous.get("version") == version else 0
    save_cursor(db, key, cursor, recorded)
    rows = db.connection.execute(
        "SELECT id FROM games WHERE id>? ORDER BY id LIMIT ?", (cursor, config.deep_max_scan + 1)
    ).fetchall()
    if not rows and cursor:
        rows = db.connection.execute(
            "SELECT id FROM games ORDER BY id LIMIT ?", (config.deep_max_scan + 1,)
        ).fetchall()
    return key, recorded, rows


def advance(db, key, version, game_id):
    save_cursor(db, key, game_id, version)


def _record(value):
    try:
        result = json.loads(value)
    except (ValueError, TypeError):
        return {}
    return result if isinstance(result, dict) else {}
