"""Bind a current created-fork counterfactual to an owned objective."""

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_contract import OWNED_HISTORY
from .objective_fork_avoidance_contract import GOAL, OBJECTIVE, VERSION
from .objective_fork_defense_budget import SOURCE_UNITS, reserve, scope
from .objective_source_budget import within_budget
from .pawn_scope import history_known
from .recurrence_snapshot import read_snapshot
from .related_fork_avoidance_source import source_for_evidence


def resolve(db, version, key, subject):
    if version != VERSION or not _valid_key(key):
        raise ValueError("fork avoidance source unavailable")
    with scope(), read_snapshot(db):
        if not within_budget(db, int(key), subject):
            raise ValueError("fork avoidance source unavailable")
        reserve(SOURCE_UNITS)
        source = source_for_evidence(db, subject, int(key))
        board = decision_board(db, position_row(db, source["provenance"]["position_id"]))
        if not history_known(board) or board.fen() != source["prompt_fen"]:
            raise ValueError("fork avoidance history unavailable")
        source["objective"] = GOAL
        source["provenance"].update(
            objective_version=OBJECTIVE,
            history_mode=OWNED_HISTORY,
            source_counterfactual=source["source_counterfactual"],
        )
        return source


def _valid_key(key):
    return (
        isinstance(key, str) and key.isdecimal() and 0 < int(key) < 2**63 and str(int(key)) == key
    )
