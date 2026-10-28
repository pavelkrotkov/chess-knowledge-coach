"""Measure a game against the per-run position budget."""

from .db import Database


def position_count(db: Database, game_id: int) -> int:
    return db.connection.execute(
        "SELECT COUNT(*) FROM positions WHERE game_id=?", (game_id,)
    ).fetchone()[0]
