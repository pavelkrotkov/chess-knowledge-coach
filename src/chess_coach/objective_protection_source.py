"""Resolve current, subject-owned evidence for one bounded protection task."""

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_capture_current import current
from .objective_protection_contract import VERSION
from .objective_protection_snapshot import snapshot
from .objective_source_budget import within_budget
from .pawn_scope import history_known


def resolve(db, version, key, subject):
    if not _valid_key(version, key) or not within_budget(db, int(key), subject):
        raise ValueError("protection objective unavailable")
    evidence_id = int(key)
    view, review = _current(db, evidence_id, subject)
    board = decision_board(db, position_row(db, view["position_id"]))
    if not history_known(board) or board.fen() != view["decision_fen"]:
        raise ValueError("protection history unavailable")
    result = snapshot(board, view, review, evidence_id)
    if (view, review) != _current(db, evidence_id, subject):
        raise ValueError("protection source changed")
    return result


def _current(db, evidence_id, subject):
    return current(db, evidence_id, subject, kind="material_protection", operation="prevent")


def _valid_key(version, key):
    return version == VERSION and key.isdecimal() and 0 < int(key) < 2**63 and str(int(key)) == key
