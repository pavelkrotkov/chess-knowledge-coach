"""Resolve a current owned mate source for a mate-in-one exercise."""

from .decision_history import decision_board
from .mate_evidence import load
from .mate_inspection_source import position_row
from .objective_mate_policy import eligible, valid_key
from .objective_mate_snapshot import snapshot
from .objective_source_budget import within_budget


def resolve(db, version, key, subject):
    if not valid_key(version, key) or not within_budget(db, int(key), subject):
        raise ValueError("mate-in-one source unavailable")
    evidence, fact, fingerprint = load(db, int(key), subject)
    if not eligible(db, evidence, fact):
        raise ValueError("mate-in-one source unavailable")
    board = decision_board(db, position_row(db, evidence["position_id"]))
    try:
        return snapshot(db, board, evidence, fact, fingerprint)
    except (TypeError, KeyError, IndexError):
        raise ValueError("mate-in-one source unavailable") from None
