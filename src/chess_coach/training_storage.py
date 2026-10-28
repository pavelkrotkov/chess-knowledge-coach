"""Persist the scheduled card and its immutable attempt metadata."""

import json
from datetime import datetime

from fsrs import Card

from .db import Database
from .training_scheduler import SCHEDULER_VERSION


def store_review(
    db: Database,
    item_id: int,
    rating: str,
    elapsed_seconds: int | None,
    now: datetime,
    updated: Card,
    config: dict,
) -> dict:
    config_json = json.dumps(config, sort_keys=True, allow_nan=False)
    due = updated.due.isoformat()
    db.connection.execute(
        """UPDATE training_items SET state=?, step=?, stability=?, difficulty=?, due=?,
        last_review=?, scheduler_version=?, scheduler_config_json=? WHERE id=?""",
        (
            updated.state.name.lower(),
            updated.step,
            updated.stability,
            updated.difficulty,
            due,
            now.isoformat(),
            SCHEDULER_VERSION,
            config_json,
            item_id,
        ),
    )
    cursor = db.connection.execute(
        """INSERT INTO training_attempts
        (item_id, rating, elapsed_seconds, reviewed_at, scheduler_version, scheduler_config_json)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (item_id, rating, elapsed_seconds, now.isoformat(), SCHEDULER_VERSION, config_json),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("SQLite did not return a training attempt ID")
    return {
        "id": item_id,
        "attempt_id": cursor.lastrowid,
        "state": updated.state.name.lower(),
        "due": due,
        "scheduler_version": SCHEDULER_VERSION,
        "scheduler_config": config,
    }
