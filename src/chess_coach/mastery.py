"""Evidence-gated, deliberately simple mastery states."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from .db import Database

MASTERY_MODEL_VERSION = "weighted-outcomes-v1"


def _score(rows: list[Any]) -> tuple[float, float]:
    effective = [row for row in rows if row["outcome"] in {"success", "failure"}]
    weight = sum(row["confidence"] for row in effective)
    score = (
        sum(row["confidence"] for row in effective if row["outcome"] == "success") / weight
        if weight
        else 0.5
    )
    return score, weight


def _observation_time(row: Any) -> datetime:
    try:
        value = datetime.fromisoformat(row["observation_at"])
    except ValueError:
        return datetime.now(UTC)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def update_mastery(
    db: Database, *, skill: str, operation: str, subject: str = "default"
) -> dict[str, Any] | None:
    rows = db.connection.execute(
        """SELECT id, outcome, confidence, context_json, observation_at
        FROM evidence_mappings
        WHERE subject = ? AND skill = ? AND operation = ? AND human_validated = 1
        ORDER BY id""",
        (subject, skill, operation),
    ).fetchall()
    state_row = db.connection.execute(
        "SELECT * FROM mastery_states WHERE subject = ? AND skill = ? AND operation = ?",
        (subject, skill, operation),
    ).fetchone()
    if not rows:
        if state_row is not None:
            db.connection.execute("DELETE FROM mastery_states WHERE id = ?", (state_row["id"],))
            db.connection.commit()
        return None

    evidence_ids = [int(row["id"]) for row in rows]
    previous_ids: list[int] = []
    if state_row is not None:
        event = db.connection.execute(
            "SELECT evidence_ids_json FROM mastery_events WHERE state_id = ? ORDER BY id DESC LIMIT 1",
            (state_row["id"],),
        ).fetchone()
        if event:
            previous_ids = json.loads(event["evidence_ids_json"])

    mastery, evidence_weight = _score(rows)
    uncertainty = 1 / (1 + evidence_weight)
    cutoff = datetime.now(UTC) - timedelta(days=30)
    recent = [row for row in rows if _observation_time(row) >= cutoff]
    older = [row for row in rows if _observation_time(row) < cutoff]
    recent_score, _ = _score(recent)
    older_score, older_weight = _score(older)
    trend = recent_score - older_score if older_weight else 0.0
    now = datetime.now(UTC).isoformat()
    previous_mastery = state_row["mastery"] if state_row is not None else None
    changed = (
        state_row is None
        or set(previous_ids) != set(evidence_ids)
        or abs(state_row["mastery"] - mastery) > 1e-12
        or abs(state_row["uncertainty"] - uncertainty) > 1e-12
        or abs(state_row["trend_30d"] - trend) > 1e-12
    )

    if state_row is None:
        db.connection.execute(
            """INSERT INTO mastery_states
            (subject, skill, operation, mastery, uncertainty, evidence_weight, trend_30d, updated_at, model_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                subject,
                skill,
                operation,
                mastery,
                uncertainty,
                evidence_weight,
                trend,
                now,
                MASTERY_MODEL_VERSION,
            ),
        )
        state_row = db.connection.execute(
            "SELECT * FROM mastery_states WHERE subject = ? AND skill = ? AND operation = ?",
            (subject, skill, operation),
        ).fetchone()
    else:
        db.connection.execute(
            """UPDATE mastery_states
            SET mastery = ?, uncertainty = ?, evidence_weight = ?, trend_30d = ?, updated_at = ?, model_version = ?
            WHERE id = ?""",
            (
                mastery,
                uncertainty,
                evidence_weight,
                trend,
                now,
                MASTERY_MODEL_VERSION,
                state_row["id"],
            ),
        )

    if changed:
        db.connection.execute(
            """INSERT INTO mastery_events
            (state_id, evidence_ids_json, previous_mastery, new_mastery, changed_at, model_version)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                state_row["id"],
                json.dumps(evidence_ids),
                previous_mastery,
                mastery,
                now,
                MASTERY_MODEL_VERSION,
            ),
        )
    db.connection.commit()
    return dict(
        db.connection.execute(
            "SELECT * FROM mastery_states WHERE id = ?", (state_row["id"],)
        ).fetchone()
    )


def mastery_report(db: Database, *, subject: str = "default") -> list[dict[str, Any]]:
    rows = db.connection.execute(
        "SELECT * FROM mastery_states WHERE subject = ? ORDER BY skill, operation", (subject,)
    ).fetchall()
    result = []
    for row in rows:
        if row["uncertainty"] > 0.25:
            state = "uncertain"
        elif row["mastery"] >= 0.8:
            state = "mastered"
        elif row["mastery"] <= 0.35:
            state = "struggling"
        else:
            state = "developing"
        event = db.connection.execute(
            "SELECT evidence_ids_json FROM mastery_events WHERE state_id = ? ORDER BY id DESC LIMIT 1",
            (row["id"],),
        ).fetchone()
        evidence_ids = json.loads(event["evidence_ids_json"]) if event else []
        contexts = []
        if evidence_ids and all(isinstance(evidence_id, int) for evidence_id in evidence_ids):
            placeholders = ",".join("?" for _ in evidence_ids)
            context_rows = db.connection.execute(
                f"SELECT id, context_json FROM evidence_mappings WHERE id IN ({placeholders})",
                evidence_ids,
            ).fetchall()
            contexts = [
                {
                    "evidence_id": context_row["id"],
                    "context": json.loads(context_row["context_json"]),
                }
                for context_row in context_rows
            ]
        result.append(
            {
                **dict(row),
                "state": state,
                "supporting_evidence_ids": evidence_ids,
                "contexts": contexts,
            }
        )
    return result
