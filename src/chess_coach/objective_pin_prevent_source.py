"""Resolve current owned pin-prevention evidence under explicit work limits."""

from .decision_history import decision_board
from .evidence_review_state import _summary, evidence_row
from .mate_inspection_source import position_row
from .material_opportunity_source import load_source
from .objective_pin_prevent_budget import scope, take_source
from .objective_pin_prevent_contract import VERSION
from .objective_pin_prevent_current import current
from .objective_pin_prevent_freshness import require_unchanged
from .objective_pin_prevent_preflight import reserve, valid_key
from .objective_pin_prevent_snapshot import snapshot
from .objective_source_budget import within_budget
from .pawn_scope import history_known
from .recurrence_snapshot import read_snapshot


def resolve(db, version, key, subject):
    with scope(), read_snapshot(db):
        return _resolve(db, version, key, subject)


def _resolve(db, version, key, subject):
    if not valid_key(version, key, VERSION) or not within_budget(db, int(key), subject):
        raise ValueError("pin prevention source unavailable")
    summary = _summary(evidence_row(db, int(key)))
    board = decision_board(db, position_row(db, summary["position_id"]))
    if not history_known(board) or board.fen() != summary["decision_fen"]:
        raise ValueError("pin prevention history unavailable")
    budget = reserve(board)
    take_source()
    evidence, fact = current(db, int(key), subject)
    if board.fen() != evidence["decision_fen"]:
        raise ValueError("pin prevention source changed")
    source = load_source(db, fact["detector_run_id"])
    result = snapshot(board, evidence, fact, source, budget)
    require_unchanged(db, evidence, fact, source)
    return result
