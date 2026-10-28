"""FSRS scheduling for atomic training items rather than abstract skills."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fsrs import Scheduler

from .db import Database
from .training_review import review_item_in_transaction as review_item_in_transaction
from .training_scheduler import SCHEDULER_VERSION as SCHEDULER_VERSION
from .training_scheduler import scheduler_config, utc
from .training_transaction import training_transaction


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
    if scheduler_version != SCHEDULER_VERSION:
        raise ValueError("scheduler_version must match the installed FSRS version")
    config = json.dumps(scheduler_config(Scheduler(enable_fuzzing=False)), sort_keys=True)
    with training_transaction(db):
        db.connection.execute(
            """INSERT OR IGNORE INTO training_items
            (source_type, source_ref, skill, operation, due, scheduler_version, scheduler_config_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                source_type,
                source_ref,
                skill,
                operation,
                datetime.now(UTC).isoformat(),
                SCHEDULER_VERSION,
                config,
            ),
        )
        row = db.connection.execute(
            """SELECT id FROM training_items WHERE source_type = ? AND source_ref = ?
            AND skill = ? AND operation = ?""",
            (source_type, source_ref, skill, operation),
        ).fetchone()
        if row is None:
            raise RuntimeError("training item was not created and does not exist")
        return int(row[0])


def review_item(
    db: Database,
    item_id: int,
    rating: str,
    *,
    elapsed_seconds: int | None = None,
    reviewed_at: datetime | None = None,
) -> dict[str, object]:
    with training_transaction(db):
        return review_item_in_transaction(
            db, item_id, rating, elapsed_seconds=elapsed_seconds, reviewed_at=reviewed_at
        )


def due_items(
    db: Database,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be 1..1000")
    at = utc(now if now is not None else datetime.now(UTC)).isoformat()
    rows = db.connection.execute(
        "SELECT * FROM training_items WHERE due <= ? ORDER BY due, id LIMIT ?", (at, limit)
    ).fetchall()
    return [dict(row) for row in rows]
