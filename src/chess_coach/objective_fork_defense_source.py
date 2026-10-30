"""Resolve one current owned fork defense with its original legal history."""

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_fork_defense_budget import SOURCE_UNITS, reserve, scope
from .objective_fork_defense_contract import VERSION
from .objective_fork_defense_snapshot import snapshot
from .objective_source_budget import within_budget
from .pawn_scope import history_known
from .recurrence_snapshot import read_snapshot
from .related_fork_prevention_source_current import current


def resolve(db, version, key, subject):
    if not _valid_key(version, key):
        raise ValueError("fork defense source unavailable")
    with scope(), read_snapshot(db):
        if not within_budget(db, int(key), subject):
            raise ValueError("fork defense source unavailable")
        reserve(SOURCE_UNITS)
        evidence = current(db, subject, int(key))
        board = decision_board(db, position_row(db, evidence["position_id"]))
        if not history_known(board) or board.fen() != evidence["decision_fen"]:
            raise ValueError("fork defense history unavailable")
        return snapshot(db, board, evidence, evidence["facts"][0])


def _valid_key(version, key):
    return (
        isinstance(key, str)
        and version == VERSION
        and key.isdecimal()
        and 0 < int(key) < 2**63
        and str(int(key)) == key
    )
