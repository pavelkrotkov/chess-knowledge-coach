"""Resolve an explicit owned mate-within-two objective with original history."""

from .decision_history import decision_board
from .mate_evidence import load
from .mate_inspection_source import position_row
from .objective_short_policy import eligible
from .objective_short_snapshot import OBJECTIVE as OBJECTIVE
from .objective_short_snapshot import snapshot
from .objective_source_budget import within_budget
from .pawn_scope import history_known

VERSION = "mate-two-own-v1"


def resolve(db, version, key, subject):
    if not _valid_key(version, key):
        raise ValueError("mate-within-two source unavailable")
    if not within_budget(db, int(key), subject):
        raise ValueError("mate-within-two source unavailable")
    evidence, fact, fingerprint = load(db, int(key), subject)
    if not eligible(db, evidence, fact):
        raise ValueError("mate-within-two source unavailable")
    board = decision_board(db, position_row(db, evidence["position_id"]))
    if not history_known(board) or board.is_game_over(claim_draw=True):
        raise ValueError("mate-within-two history unavailable")
    return snapshot(db, board, evidence, fact, fingerprint)


def _valid_key(version, key):
    return version == VERSION and key.isdecimal() and 0 < int(key) < 2**63 and str(int(key)) == key
