"""Resolve an owned fork objective with full original game history."""

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_fork_contract import MISS_OBJECTIVE, MISS_VERSION, OBJECTIVE, VERSION
from .objective_fork_current import current
from .objective_fork_snapshot import snapshot
from .objective_source_budget import within_budget
from .pawn_scope import history_known


def resolve(db, version, key, subject):
    if not _valid_key(version, key) or not within_budget(db, int(key), subject):
        raise ValueError("fork objective unavailable")
    evidence, fact = current(db, int(key), subject)
    board = decision_board(db, position_row(db, evidence["position_id"]))
    if not history_known(board) or board.fen() != evidence["decision_fen"]:
        raise ValueError("fork history unavailable")
    result = snapshot(
        db,
        board,
        evidence,
        fact,
        objective=MISS_OBJECTIVE if version == MISS_VERSION else OBJECTIVE,
    )
    if (evidence, fact) != current(db, int(key), subject):
        raise ValueError("fork source changed")
    return result


def _valid_key(version, key):
    return (
        isinstance(key, str)
        and version in {VERSION, MISS_VERSION}
        and key.isdecimal()
        and 0 < int(key) < 2**63
        and str(int(key)) == key
    )
