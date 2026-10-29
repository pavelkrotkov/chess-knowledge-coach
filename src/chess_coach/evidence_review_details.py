"""Detailed evidence context, source facts, and review history."""

from __future__ import annotations

from .back_rank_evidence import currentness as back_rank_currentness
from .db import Database
from .discovery_review_view import apply as discovery_view
from .evidence_review_facts import facts_for_evidence
from .evidence_review_json import decode
from .evidence_review_state import _summary, evidence_row
from .fork_defense_evidence import current_defense
from .fork_defense_explanation import explain as explain_defense
from .fork_evidence_current import current_fork
from .fork_explanation import explain_fork
from .king_safety_current import currentness as king_safety_currentness
from .mate_evidence import currentness as mate_currentness
from .material_evidence_current import evidence_currentness
from .material_explanation import explain_material
from .pawn_coach_current import current_pawn
from .pawn_coach_explanation import explain as explain_pawn
from .pawn_structure_current import currentness as structure_currentness
from .pin_evidence import current_pin
from .pin_explanation import explain as explain_pin
from .rook_plan_current import currentness as rook_currentness


def inspect_evidence(db: Database, evidence_id: int, *, _history=None) -> dict:
    row = evidence_row(db, evidence_id)
    result = _summary(row)
    result["context"] = decode(row["context_json"])
    result["material_explanation"] = explain_material(result["context"])
    result["mapping_scope"] = row["scope_key"]
    result["mapping_created_at"] = row["mapping_created_at"]
    result["facts"] = facts_for_evidence(db, evidence_id)
    result["material_source_currentness"] = evidence_currentness(db, result)
    fact, currentness, fen = current_fork(db, result, _history=_history)
    result["fork_explanation"] = explain_fork(fact, fen)
    result["fork_source_currentness"] = currentness
    if currentness == "current":
        result["decision_fen"] = fen
    defense, defense_currentness, defense_fen = current_defense(db, result, _history=_history)
    result["fork_defense_explanation"] = explain_defense(defense, defense_fen)
    result["fork_defense_currentness"] = defense_currentness
    if defense_currentness == "current":
        result["decision_fen"] = defense_fen
    discovery_view(db, result, _history=_history)
    result["mate_source_currentness"] = mate_currentness(db, result)
    pawn, pawn_currentness = current_pawn(db, result)
    result["pawn_source_currentness"] = pawn_currentness
    result["pawn_explanation"] = explain_pawn(pawn) if pawn else None
    if pawn:
        result["decision_fen"] = pawn["report"]["decision_fen"]
    result["back_rank_source_currentness"] = back_rank_currentness(db, result)

    result["king_safety_currentness"] = king_safety_currentness(db, result, _history=_history)
    result["pawn_structure_currentness"] = structure_currentness(db, result, _history=_history)
    for operation in ("execute", "prevent"):
        pin, currentness, pin_fen = current_pin(db, result, operation, _history=_history)
        if currentness:
            result["pin_explanation"] = explain_pin(pin, pin_fen)
            result["pin_source_currentness"] = currentness
            if currentness == "current":
                result["decision_fen"] = pin_fen
    result["rook_plan_currentness"] = rook_currentness(db, result, _history=_history)
    result["reviews"] = _reviews(db, evidence_id)
    return result


def _reviews(db: Database, evidence_id: int) -> list[dict]:
    rows = db.connection.execute(
        """SELECT id, decision, actor, rationale, reviewed_at
        FROM evidence_review_events WHERE evidence_id = ? ORDER BY id""",
        (evidence_id,),
    ).fetchall()
    return [dict(row) for row in rows]
