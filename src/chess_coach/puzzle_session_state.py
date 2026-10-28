"""Load and present the public state of a puzzle attempt."""

from __future__ import annotations

from datetime import UTC, datetime
from sqlite3 import Row

from .db import Database


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _session(db: Database, attempt_id: str) -> Row:
    row = db.connection.execute(
        "SELECT * FROM puzzle_sessions WHERE attempt_id = ?", (attempt_id,)
    ).fetchone()
    if row is None:
        raise ValueError("unknown puzzle attempt")
    return row


def _view(row: Row) -> dict[str, object]:
    return {
        "attempt_id": row["attempt_id"],
        "corpus_version": row["corpus_version"],
        "puzzle_id": row["puzzle_id"],
        "fen": row["current_fen"],
        "status": row["status"],
        "hints_used": row["hints_used"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


def show_attempt(db: Database, attempt_id: str) -> dict[str, object]:
    return _view(_session(db, attempt_id))
