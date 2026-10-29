"""Detailed evidence context, source facts, and review history."""

from __future__ import annotations

from .db import Database
from .evidence_review_facts import facts_for_evidence
from .evidence_review_json import decode
from .evidence_review_state import _summary, evidence_row
from .material_explanation import explain_material


def inspect_evidence(db: Database, evidence_id: int) -> dict:
    row = evidence_row(db, evidence_id)
    result = _summary(row)
    result["context"] = decode(row["context_json"])
    result["material_explanation"] = explain_material(result["context"])
    result["mapping_scope"] = row["scope_key"]
    result["mapping_created_at"] = row["mapping_created_at"]
    result["facts"] = facts_for_evidence(db, evidence_id)
    result["reviews"] = _reviews(db, evidence_id)
    return result


def _reviews(db: Database, evidence_id: int) -> list[dict]:
    rows = db.connection.execute(
        """SELECT id, decision, actor, rationale, reviewed_at
        FROM evidence_review_events WHERE evidence_id = ? ORDER BY id""",
        (evidence_id,),
    ).fetchall()
    return [dict(row) for row in rows]
