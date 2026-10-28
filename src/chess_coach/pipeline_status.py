"""Read durable, sanitized per-game processing progress without triggering work."""

from collections import Counter

from .db import Database


def pipeline_status(db: Database) -> dict:
    rows = db.connection.execute("""SELECT game_id,stage,status,detail,updated_at
        FROM pipeline_stages ORDER BY game_id,stage""").fetchall()
    stages = [dict(row) for row in rows]
    health = db.connection.execute(
        "SELECT status,started_at,finished_at,last_success_at,sync_status,sync_detail,sync_at,last_sync_success_at,retry_until FROM pipeline_health WHERE id=1"
    ).fetchone()
    return {
        "health": dict(health) if health is not None else None,
        "stages": stages,
        "counts": dict(sorted(Counter(row["status"] for row in rows).items())),
    }
