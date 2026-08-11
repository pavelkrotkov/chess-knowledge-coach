"""FSRS scheduling for atomic training items rather than abstract skills."""

from __future__ import annotations

from datetime import UTC, datetime

from fsrs import Card, Rating, Scheduler, State

from .db import Database

SCHEDULER_VERSION = "fsrs-5-defaults-0.1.0"
_RATINGS = {"again": Rating.Again, "hard": Rating.Hard, "good": Rating.Good, "easy": Rating.Easy}


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def create_training_item(
    db: Database,
    *,
    source_type: str,
    source_ref: str,
    skill: str,
    operation: str,
    scheduler_version: str = SCHEDULER_VERSION,
) -> int:
    now = datetime.now(UTC)
    db.connection.execute(
        """INSERT OR IGNORE INTO training_items
        (source_type, source_ref, skill, operation, due, scheduler_version)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (source_type, source_ref, skill, operation, _iso(now), scheduler_version),
    )
    row = db.connection.execute(
        "SELECT id FROM training_items WHERE source_type = ? AND source_ref = ? AND skill = ? AND operation = ?",
        (source_type, source_ref, skill, operation),
    ).fetchone()
    if row is None:
        raise RuntimeError("training item was not created")
    db.connection.commit()
    return int(row[0])


def review_item(
    db: Database,
    item_id: int,
    rating: str,
    *,
    elapsed_seconds: int | None = None,
    reviewed_at: datetime | None = None,
) -> dict[str, object]:
    if rating not in _RATINGS:
        raise ValueError("rating must be again, hard, good, or easy")
    row = db.connection.execute("SELECT * FROM training_items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise ValueError(f"unknown training item: {item_id}")
    now = reviewed_at or datetime.now(UTC)
    card = Card(
        card_id=item_id,
        state=State[row["state"].capitalize()],
        step=row["step"],
        stability=row["stability"],
        difficulty=row["difficulty"],
        due=datetime.fromisoformat(row["due"]),
        last_review=datetime.fromisoformat(row["last_review"]) if row["last_review"] else None,
    )
    updated, _ = Scheduler(enable_fuzzing=False).review_card(
        card, _RATINGS[rating], review_datetime=now, review_duration=elapsed_seconds
    )
    db.connection.execute(
        """UPDATE training_items SET state = ?, step = ?, stability = ?, difficulty = ?, due = ?, last_review = ? WHERE id = ?""",
        (
            updated.state.name.lower(),
            updated.step,
            updated.stability,
            updated.difficulty,
            _iso(updated.due),
            _iso(now),
            item_id,
        ),
    )
    db.connection.execute(
        "INSERT INTO training_attempts(item_id, rating, elapsed_seconds, reviewed_at, scheduler_version) VALUES (?, ?, ?, ?, ?)",
        (item_id, rating, elapsed_seconds, _iso(now), row["scheduler_version"]),
    )
    db.connection.commit()
    return {
        "id": item_id,
        "state": updated.state.name.lower(),
        "due": _iso(updated.due),
        "scheduler_version": row["scheduler_version"],
    }


def due_items(
    db: Database, *, now: datetime | None = None, limit: int = 100
) -> list[dict[str, object]]:
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be 1..1000")
    at = _iso(now or datetime.now(UTC))
    rows = db.connection.execute(
        "SELECT * FROM training_items WHERE due <= ? ORDER BY due, id LIMIT ?", (at, limit)
    ).fetchall()
    return [dict(row) for row in rows]
