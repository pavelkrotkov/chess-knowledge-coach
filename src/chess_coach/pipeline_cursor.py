"""Rotate bounded game scans across runs without storing account names."""

from datetime import UTC, datetime

from .db import Database
from .lichess_state import account_key
from .mapping_transaction import mapping_transaction


def scan_from(db: Database, learner: str, limit: int, scan_hash: str):
    key = account_key(learner.strip())
    row = db.connection.execute(
        "SELECT last_game_id,scan_hash FROM pipeline_cursors WHERE account_key=?", (key,)
    ).fetchone()
    cursor = row[0] if row and row[1] == scan_hash else 0
    games = db.connection.execute(
        "SELECT * FROM games WHERE id>? ORDER BY id LIMIT ?", (cursor, limit)
    ).fetchall()
    if not games and cursor:
        games = db.connection.execute(
            "SELECT * FROM games ORDER BY id LIMIT ?", (limit,)
        ).fetchall()
    return key, games


def save_cursor(db: Database, key: str, game_id: int, scan_hash: str) -> None:
    with mapping_transaction(db):
        db.connection.execute(
            """INSERT INTO pipeline_cursors(account_key,last_game_id,updated_at,scan_hash)
            VALUES (?,?,?,?) ON CONFLICT(account_key) DO UPDATE SET
            last_game_id=excluded.last_game_id,updated_at=excluded.updated_at,
            scan_hash=excluded.scan_hash""",
            (key, game_id, datetime.now(UTC).isoformat(), scan_hash),
        )


def has_more(db: Database, games, scanned: int, last_game: int) -> bool:
    if len(games) > scanned:
        return True
    if not scanned:
        return False
    return (
        db.connection.execute("SELECT 1 FROM games WHERE id>? LIMIT 1", (last_game,)).fetchone()
        is not None
    )
