"""Resolve current, subject-owned evidence for one bounded protection task."""

from .objective_capture_current import current
from .objective_protection_contract import VERSION
from .objective_protection_history import board_for
from .objective_protection_snapshot import snapshot
from .objective_source_budget import within_budget
from .pawn_scope import history_known


def resolve(db, version, key, subject, *, _verified_board=None, _history=None):
    if not _valid_key(version, key) or not within_budget(db, int(key), subject):
        raise ValueError("protection objective unavailable")
    evidence_id = int(key)
    view, review = _current(db, evidence_id, subject, _history)
    board = board_for(db, view, _verified_board, _history)
    if not history_known(board) or board.fen() != view["decision_fen"]:
        raise ValueError("protection history unavailable")
    result = snapshot(board, view, review, evidence_id)
    if (view, review) != _current(db, evidence_id, subject, _history):
        raise ValueError("protection source changed")
    return result


def _current(db, evidence_id, subject, _history):
    return current(
        db, evidence_id, subject, kind="material_protection", operation="prevent", _history=_history
    )


def _valid_key(version, key):
    return version == VERSION and key.isdecimal() and 0 < int(key) < 2**63 and str(int(key)) == key
