"""Read evidence identity, lifecycle, and current review state."""

from __future__ import annotations

from sqlite3 import Row

from .db import Database
from .evidence_review_facts import facts_for_evidence
from .evidence_review_json import decision_fen, decode, legacy_status, legacy_validation

_SELECT = """
SELECT e.*, p.game_id, p.ply, p.fen AS position_fen,
       r.status AS run_status, r.producer AS mapping_producer,
       r.scope_key, r.created_at AS mapping_created_at,
       v.decision AS review_decision, v.actor AS review_actor,
       v.reviewed_at AS review_time, v.rationale AS review_rationale
FROM evidence_mappings e
LEFT JOIN positions p ON p.id = e.position_id
LEFT JOIN mapping_runs r ON r.id = e.mapping_run_id
LEFT JOIN evidence_review_events v ON v.id = (
    SELECT id FROM evidence_review_events
    WHERE evidence_id = e.id ORDER BY id DESC LIMIT 1
)
"""


def _status(row: Row) -> str:
    if row["review_decision"] is not None:
        return {"accept": "accepted", "reject": "rejected", "revoke": "revoked"}[
            row["review_decision"]
        ]
    return legacy_status(row["human_validated"])


def _lifecycle(row: Row) -> str:
    if row["mapping_run_id"] is None:
        return "unscoped"
    return row["run_status"] or "unknown"


def _summary(row: Row) -> dict:
    context = decode(row["context_json"])
    return {
        "id": row["id"],
        "position_id": row["position_id"],
        "game_id": row["game_id"],
        "ply": row["ply"],
        "position_fen": row["position_fen"],
        "decision_fen": decision_fen(context),
        "subject": row["subject"],
        "skill": row["skill"],
        "operation": row["operation"],
        "outcome": row["outcome"],
        "confidence": row["confidence"],
        "source_facts": decode(row["source_facts_json"]),
        "source_provenance": row["source_provenance"],
        "mapper_version": row["mapper_version"],
        "mapping_producer": row["mapping_producer"],
        "mapping_run_id": row["mapping_run_id"],
        "lifecycle_status": _lifecycle(row),
        "review_status": _status(row),
        "legacy_validation": legacy_validation(row["legacy_validated"]),
        "review_actor": row["review_actor"],
        "reviewed_at": row["review_time"],
        "observation_at": row["observation_at"],
    }


def list_evidence(db: Database, *, after_id: int = 0, limit: int = 100) -> list[dict]:
    if after_id < 0 or not 1 <= limit <= 1000:
        raise ValueError("after_id must be non-negative and limit must be 1..1000")
    rows = db.connection.execute(
        _SELECT + " WHERE e.id > ? ORDER BY e.id LIMIT ?", (after_id, limit)
    ).fetchall()
    return [_with_facts(db, row) for row in rows]


def evidence_row(db: Database, evidence_id: int) -> Row:
    row = db.connection.execute(_SELECT + " WHERE e.id = ?", (evidence_id,)).fetchone()
    if row is None:
        raise ValueError(f"unknown evidence id: {evidence_id}")
    return row


def _with_facts(db: Database, row: Row) -> dict:
    return {**_summary(row), "facts": facts_for_evidence(db, row["id"])}
