"""Resolve a current owned pawn decision with its full original history."""

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_pawn_contract import VERSION
from .objective_pawn_snapshot import snapshot
from .objective_source_budget import within_budget
from .pawn_practice import _view
from .pawn_practice_keys import evidence_id
from .pawn_scope import history_known, supported


def resolve(db, version, key, subject):
    item = evidence_id(key)
    if version != VERSION or not within_budget(db, item, subject):
        raise ValueError("pawn objective unavailable")
    evidence = _view(db, item, subject)
    review = _review(db, item)
    board = decision_board(db, position_row(db, evidence["position_id"]))
    if not supported(board) or not history_known(board) or board.is_game_over(claim_draw=True):
        raise ValueError("pawn history unavailable")
    if board.fen() != evidence["decision_fen"]:
        raise ValueError("pawn source changed")
    result = snapshot(board, evidence, review)
    if _signature(evidence, review) != _signature(_view(db, item, subject), _review(db, item)):
        raise ValueError("pawn source changed")
    return result


def _review(db, item):
    row = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (item,),
    ).fetchone()
    return row["id"] if row else None


def _signature(evidence, review):
    return (
        evidence["id"],
        evidence["position_id"],
        evidence["mapping_run_id"],
        evidence["review_status"],
        review,
        evidence["context"],
    )
