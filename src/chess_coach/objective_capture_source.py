"""Resolve a current owned material source into an explicit bounded objective."""

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_capture_contract import VERSIONS
from .objective_capture_current import current
from .objective_capture_snapshot import snapshot
from .objective_source_budget import within_budget
from .pawn_scope import history_known


def resolve(db, version, key, subject):
    if not _valid_key(version, key) or not within_budget(db, int(key), subject):
        raise ValueError("capture objective unavailable")
    evidence_id = int(key)
    view, review = current(db, evidence_id, subject)
    board = decision_board(db, position_row(db, view["position_id"]))
    if not history_known(board) or board.fen() != view["decision_fen"]:
        raise ValueError("capture history unavailable")
    result = snapshot(board, view, review, evidence_id, version)
    if (view, review) != current(db, evidence_id, subject):
        raise ValueError("capture source changed")
    return result


def _valid_key(version, key):
    return version in VERSIONS and key.isdecimal() and 0 < int(key) < 2**63 and str(int(key)) == key
