"""Persist mastery conclusions and append their evidence history."""

import json
from datetime import UTC, datetime

from .db import Database


def write_state(
    db: Database, subject: str, skill: str, operation: str, state, values: dict, version: str
) -> dict:
    previous_ids = _previous_ids(db, state)
    changed = _changed(state, values, previous_ids)
    previous = state["mastery"] if state is not None else None
    now = datetime.now(UTC).isoformat()
    db.connection.execute(
        """INSERT INTO mastery_states
        (subject, skill, operation, mastery, uncertainty, evidence_weight, trend_30d,
         updated_at, model_version, is_stale)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ON CONFLICT(subject, skill, operation) DO UPDATE SET
        mastery=excluded.mastery, uncertainty=excluded.uncertainty,
        evidence_weight=excluded.evidence_weight, trend_30d=excluded.trend_30d,
        updated_at=excluded.updated_at, model_version=excluded.model_version, is_stale=0""",
        (
            subject,
            skill,
            operation,
            values["mastery"],
            values["uncertainty"],
            values["evidence_weight"],
            values["trend_30d"],
            now,
            version,
        ),
    )
    result = db.connection.execute(
        "SELECT * FROM mastery_states WHERE subject = ? AND skill = ? AND operation = ?",
        (subject, skill, operation),
    ).fetchone()
    if changed:
        db.connection.execute(
            """INSERT INTO mastery_events
            (state_id, evidence_ids_json, previous_mastery, new_mastery, changed_at, model_version)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                result["id"],
                json.dumps(values["evidence_ids"]),
                previous,
                values["mastery"],
                now,
                version,
            ),
        )
    db.connection.commit()
    return dict(result)


def _previous_ids(db: Database, state) -> list[int]:
    if state is None:
        return []
    event = db.connection.execute(
        "SELECT evidence_ids_json FROM mastery_events WHERE state_id = ? ORDER BY id DESC LIMIT 1",
        (state["id"],),
    ).fetchone()
    return json.loads(event["evidence_ids_json"]) if event else []


def _changed(state, values: dict, previous_ids: list[int]) -> bool:
    if state is None or set(previous_ids) != set(values["evidence_ids"]):
        return True
    return any(
        abs(state[key] - values[key]) > 1e-12 for key in ("mastery", "uncertainty", "trend_30d")
    )
