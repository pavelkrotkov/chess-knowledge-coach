"""Detailed evidence context, source facts, and review history."""

from __future__ import annotations

from .db import Database
from .evidence_review_facts import facts_for_evidence
from .evidence_review_json import decode
from .evidence_review_state import _summary, evidence_row
from .fork_defense_evidence import current_defense
from .fork_defense_explanation import explain as explain_defense
from .fork_evidence_current import current_fork
from .fork_explanation import explain_fork
from .mate_evidence import currentness as mate_currentness
from .material_evidence_current import evidence_currentness
from .material_explanation import explain_material


def inspect_evidence(db: Database, evidence_id: int) -> dict:
    row = evidence_row(db, evidence_id)
    result = _summary(row)
    result["context"] = decode(row["context_json"])
    result["material_explanation"] = explain_material(result["context"])
    result["mapping_scope"] = row["scope_key"]
    result["mapping_created_at"] = row["mapping_created_at"]
    result["facts"] = facts_for_evidence(db, evidence_id)
    result["material_source_currentness"] = evidence_currentness(db, result)
    fact, currentness, fen = current_fork(db, result)
    result["fork_explanation"] = explain_fork(fact, fen)
    result["fork_source_currentness"] = currentness
    if currentness == "current":
        result["decision_fen"] = fen
    defense, defense_currentness, defense_fen = current_defense(db, result)
    result["fork_defense_explanation"] = explain_defense(defense, defense_fen)
    result["fork_defense_currentness"] = defense_currentness
    if defense_currentness == "current":
        result["decision_fen"] = defense_fen
    result["mate_source_currentness"] = mate_currentness(db, result)
    result["reviews"] = _reviews(db, evidence_id)
    return result


def _reviews(db: Database, evidence_id: int) -> list[dict]:
    rows = db.connection.execute(
        """SELECT id, decision, actor, rationale, reviewed_at
        FROM evidence_review_events WHERE evidence_id = ? ORDER BY id""",
        (evidence_id,),
    ).fetchall()
    return [dict(row) for row in rows]
