"""Evidence-gated, deliberately simple mastery states."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from .db import Database


def update_mastery(db: Database, *, skill: str, operation: str) -> dict[str, Any] | None:
    rows = db.connection.execute(
        """SELECT id, outcome, confidence, context_json, created_at
        FROM evidence_mappings
        WHERE skill = ? AND operation = ? AND human_validated = 1
        ORDER BY id""",
        (skill, operation),
    ).fetchall()
    if not rows:
        return None
    state_row = db.connection.execute(
        "SELECT * FROM mastery_states WHERE skill = ? AND operation = ?", (skill, operation)
    ).fetchone()
    previous_ids: set[int] = set()
    if state_row is not None:
        event = db.connection.execute(
            "SELECT evidence_ids_json FROM mastery_events WHERE state_id = ? ORDER BY id DESC LIMIT 1",
            (state_row["id"],),
        ).fetchone()
        if event:
            previous_ids = set(json.loads(event["evidence_ids_json"]))
    new_rows = [row for row in rows if row["id"] not in previous_ids]
    if not new_rows and state_row is not None:
        return dict(state_row)

    weighted_total = sum(row["confidence"] for row in rows)
    weighted_score = sum(
        row["confidence"]
        * (1 if row["outcome"] == "success" else 0 if row["outcome"] == "failure" else 0.5)
        for row in rows
    )
    mastery = weighted_score / weighted_total if weighted_total else 0.5
    uncertainty = 1 / (1 + weighted_total)
    cutoff = datetime.now(UTC) - timedelta(days=30)
    recent = []
    older = []
    for row in rows:
        try:
            created = datetime.fromisoformat(row["created_at"]).replace(tzinfo=UTC)
        except ValueError:
            created = datetime.now(UTC)
        (recent if created >= cutoff else older).append(row)

    def score(items: list[Any]) -> float:
        weight = sum(row["confidence"] for row in items)
        return (
            sum(
                row["confidence"]
                * (1 if row["outcome"] == "success" else 0 if row["outcome"] == "failure" else 0.5)
                for row in items
            )
            / weight
            if weight
            else 0.5
        )

    trend = score(recent) - score(older) if older else 0.0
    now = datetime.now(UTC).isoformat()
    if state_row is None:
        db.connection.execute(
            """INSERT INTO mastery_states(skill, operation, mastery, uncertainty, evidence_weight, trend_30d, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (skill, operation, mastery, uncertainty, weighted_total, trend, now),
        )
        state_row = db.connection.execute(
            "SELECT * FROM mastery_states WHERE skill = ? AND operation = ?", (skill, operation)
        ).fetchone()
    else:
        db.connection.execute(
            """UPDATE mastery_states SET mastery = ?, uncertainty = ?, evidence_weight = ?, trend_30d = ?, updated_at = ? WHERE id = ?""",
            (mastery, uncertainty, weighted_total, trend, now, state_row["id"]),
        )
    db.connection.execute(
        """INSERT INTO mastery_events(state_id, evidence_ids_json, previous_mastery, new_mastery, changed_at)
        VALUES (?, ?, ?, ?, ?)""",
        (
            state_row["id"],
            json.dumps([row["id"] for row in rows]),
            state_row["mastery"] if state_row else None,
            mastery,
            now,
        ),
    )
    db.connection.commit()
    return dict(
        db.connection.execute(
            "SELECT * FROM mastery_states WHERE id = ?", (state_row["id"],)
        ).fetchone()
    )


def mastery_report(db: Database) -> list[dict[str, Any]]:
    rows = db.connection.execute(
        "SELECT * FROM mastery_states ORDER BY skill, operation"
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
        if evidence_ids:
            placeholders = ",".join("?" for _ in evidence_ids)
            contexts = db.connection.execute(
                f"SELECT context_json FROM evidence_mappings WHERE id IN ({placeholders})",
                evidence_ids,
            ).fetchall()
        context: dict[str, Any] = {}
        for item in contexts:
            context.update(json.loads(item["context_json"]))
        result.append(
            {
                **dict(row),
                "state": state,
                "supporting_evidence_ids": evidence_ids,
                "context": context,
            }
        )
    return result
