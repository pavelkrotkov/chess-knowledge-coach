"""Resolve a source-bound pin objective with its complete known history."""

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .material_opportunity_source import load_source
from .objective_pin_contract import VERSION
from .objective_pin_current import current
from .objective_pin_prevent_freshness import require_unchanged
from .objective_pin_snapshot import snapshot
from .objective_source_budget import within_budget
from .pawn_scope import history_known


def resolve(db, version, key, subject):
    if not _valid_key(version, key) or not within_budget(db, int(key), subject):
        raise ValueError("pin objective unavailable")
    evidence, fact = current(db, int(key), subject)
    board = decision_board(db, position_row(db, evidence["position_id"]))
    if not history_known(board) or board.fen() != evidence["decision_fen"]:
        raise ValueError("pin history unavailable")
    source = load_source(db, fact["detector_run_id"])
    result = snapshot(db, board, evidence, fact)
    require_unchanged(db, evidence, fact, source)
    return result


def _valid_key(version, key):
    return (
        isinstance(key, str)
        and version == VERSION
        and key.isdecimal()
        and 0 < int(key) < 2**63
        and str(int(key)) == key
    )
