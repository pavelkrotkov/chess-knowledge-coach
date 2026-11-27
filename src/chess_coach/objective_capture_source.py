"""Resolve a current owned material source into an explicit bounded objective."""

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_capture_contract import valid_key
from .objective_capture_current import current
from .objective_capture_snapshot import _snapshot
from .objective_source_budget import within_budget
from .pawn_scope import history_known


def resolve(db, version, key, subject, *, check=None, _history=None):
    if not valid_key(version, key) or not within_budget(db, int(key), subject):
        raise ValueError("capture objective unavailable")
    _check(check)
    evidence_id = int(key)
    options = {"check": check, "_history": _history}
    view, review = current(db, evidence_id, subject, **options)
    position = position_row(db, view["position_id"])
    board = (
        decision_board(db, position)
        if _history is None
        else _history.board(position["game_id"], view["position_id"])
    )
    if not history_known(board) or board.fen() != view["decision_fen"]:
        raise ValueError("capture history unavailable")
    result = _snapshot(board, view, review, evidence_id, version)
    _check(check)
    if (view, review) != current(db, evidence_id, subject, **options):
        raise ValueError("capture source changed")
    _check(check)
    return result


def _check(check):
    if check is not None:
        check()
