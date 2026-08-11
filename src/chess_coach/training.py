"""FSRS scheduling for atomic training items rather than abstract skills."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib.metadata import version as package_version

from fsrs import Card, Rating, Scheduler, State

from .db import Database

SCHEDULER_VERSION = f"fsrs-{package_version('fsrs')}-default-scheduler"
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
    if not source_type or not source_ref or not skill or not operation:
        raise ValueError("source_type, source_ref, skill, and operation must not be empty")
    now = datetime.now(UTC)
    try:
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
            raise RuntimeError("training item was not created and does not exist")
        db.connection.commit()
        return int(row[0])
    except Exception:
        db.connection.rollback()
        raise


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
    if elapsed_seconds is not None and elapsed_seconds < 0:
        raise ValueError("elapsed_seconds must be non-negative")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        row = db.connection.execute(
            "SELECT * FROM training_items WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown training item: {item_id}")
        now = reviewed_at or datetime.now(UTC)
        try:
            state = State[row["state"].capitalize()]
        except KeyError as exc:
            raise ValueError(f"invalid training item state: {row['state']}") from exc
        try:
            due = datetime.fromisoformat(row["due"])
            last_review = datetime.fromisoformat(row["last_review"]) if row["last_review"] else None
        except ValueError as exc:
            raise ValueError(f"invalid training item timestamp for item {item_id}") from exc
        card = Card(
            card_id=item_id,
            state=state,
            step=row["step"],
            stability=row["stability"],
            difficulty=row["difficulty"],
            due=due,
            last_review=last_review,
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
            (item_id, rating, elapsed_seconds, _iso(now), SCHEDULER_VERSION),
        )
        db.connection.commit()
        return {
            "id": item_id,
            "state": updated.state.name.lower(),
            "due": _iso(updated.due),
            "scheduler_version": SCHEDULER_VERSION,
        }
    except Exception:
        db.connection.rollback()
        raise


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
