"""Persist sufficient estimates and append their evidence history atomically."""

import json
from datetime import datetime

from .db import Database


def write_state(
    db: Database,
    subject: str,
    skill: str,
    operation: str,
    state,
    values: dict,
    version: str,
    now: datetime,
) -> dict:
    previous_ids = _previous_ids(db, state)
    changed = _changed(state, values, previous_ids, version)
    previous = state["mastery"] if state is not None else None
    stamp = now.isoformat()
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
            values["effective_weight"],
            values["trend_30d"],
            stamp,
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
                json.dumps(values["supporting_evidence_ids"]),
                previous,
                values["mastery"],
                stamp,
                version,
            ),
        )
    return dict(result)


def _previous_ids(db: Database, state) -> list[int]:
    if state is None:
        return []
    event = db.connection.execute(
        "SELECT evidence_ids_json FROM mastery_events WHERE state_id = ? ORDER BY id DESC LIMIT 1",
        (state["id"],),
    ).fetchone()
    return json.loads(event["evidence_ids_json"]) if event else []


def _changed(state, values: dict, previous_ids: list[int], version: str) -> bool:
    if state is None or state["is_stale"] or state["model_version"] != version:
        return True
    if set(previous_ids) != set(values["supporting_evidence_ids"]):
        return True
    pairs = (
        ("mastery", "mastery"),
        ("uncertainty", "uncertainty"),
        ("evidence_weight", "effective_weight"),
        ("trend_30d", "trend_30d"),
    )
    return any(_different(state[key], values[value]) for key, value in pairs)


def _different(left, right) -> bool:
    if left is None or right is None:
        return left is not right
    return abs(left - right) > 1e-12
