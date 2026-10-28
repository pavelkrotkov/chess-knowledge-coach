"""Read non-stale mastery states with their supporting evidence."""

import json
from typing import Any

from .db import Database


def mastery_report(db: Database, *, subject: str = "default") -> list[dict[str, Any]]:
    rows = db.connection.execute(
        "SELECT * FROM mastery_states WHERE subject = ? AND is_stale = 0 ORDER BY skill, operation",
        (subject,),
    ).fetchall()
    result = []
    for row in rows:
        state = _label(row)
        evidence_ids, contexts = _support(db, row["id"])
        result.append(
            {
                **dict(row),
                "state": state,
                "supporting_evidence_ids": evidence_ids,
                "contexts": contexts,
            }
        )
    return result


def _label(row) -> str:
    if row["uncertainty"] > 0.25:
        return "uncertain"
    if row["mastery"] >= 0.8:
        return "mastered"
    if row["mastery"] <= 0.35:
        return "struggling"
    return "developing"


def _support(db: Database, state_id: int) -> tuple[list, list]:
    event = db.connection.execute(
        "SELECT evidence_ids_json FROM mastery_events WHERE state_id = ? ORDER BY id DESC LIMIT 1",
        (state_id,),
    ).fetchone()
    evidence_ids = json.loads(event["evidence_ids_json"]) if event else []
    if not evidence_ids or not all(isinstance(item, int) for item in evidence_ids):
        return evidence_ids, []
    placeholders = ",".join("?" for _ in evidence_ids)
    rows = db.connection.execute(
        f"SELECT id, context_json FROM evidence_mappings WHERE id IN ({placeholders})", evidence_ids
    ).fetchall()
    return evidence_ids, [
        {"evidence_id": row["id"], "context": json.loads(row["context_json"])} for row in rows
    ]
