"""Prove a current exact owned-capture source in the bounded worker."""

from .decision_history import decision_board
from .fact_fingerprint import canonical, digest
from .mate_inspection_source import position_row
from .material_opportunity_current import verify_current
from .material_opportunity_loading import load
from .material_opportunity_view import build_view
from .material_source_marker import source_marker
from .objective_capture_contract import TARGET_VERSION
from .objective_capture_current import require_mapping
from .objective_capture_snapshot import qualify
from .objective_source_budget import within_budget
from .pawn_scope import history_known
from .unified_own_game_evidence import _reasons, _review


def identity(evidence, fact, source, review):
    return digest(canonical([evidence, fact, source, dict(review) if review else None]))


def prove(db, subject, evidence_id, check):
    if not within_budget(db, evidence_id, subject):
        raise ValueError("capture source unavailable")
    evidence, fact, source = load(db, evidence_id, subject)
    review = _review(db, evidence_id)
    before = identity(evidence, fact, source, review)
    view = build_view(evidence, fact, source)
    verify_current(db, subject, evidence, fact, source, view, check=check)
    if _reasons(view) or view["objective"]["kind"] != "material_capture":
        raise ValueError("capture source unavailable")
    require_mapping(db, view, "execute")
    board = decision_board(db, position_row(db, view["position_id"]))
    if not history_known(board) or board.fen() != view["decision_fen"]:
        raise ValueError("capture history unavailable")
    snapshot, proof = qualify(board, view, review, evidence_id, TARGET_VERSION, check=check)
    check()
    after = identity(*load(db, evidence_id, subject), _review(db, evidence_id))
    marker = source_marker(db, view["position_id"], view["game_id"], subject)
    if before != after or marker != view["source_fingerprint"]:
        raise ValueError("capture source changed")
    return {
        "input": before,
        "witness": view["objective_witness"],
        "snapshot": snapshot,
        "proof": proof,
    }
