"""Offer current owned discovered-mate defenses for private practice."""

from .decision_history import decision_board
from .discovery_defense_contract import PRACTICE
from .discovery_defense_practice_check import source
from .mate_inspection_source import position_row
from .material_source_marker import source_marker
from .objective_defense_snapshot import snapshot
from .objective_source_budget import within_budget


def resolve(db, version, key, subject):
    if (
        version != PRACTICE
        or not key.isdecimal()
        or not 0 < int(key) < 2**63
        or str(int(key)) != key
    ):
        raise ValueError("discovery defense unavailable")
    if not within_budget(db, int(key), subject):
        raise ValueError("discovery defense unavailable")
    evidence = source(db, int(key), subject)
    marker = source_marker(db, evidence["position_id"], evidence["game_id"], subject)
    board = decision_board(db, position_row(db, evidence["position_id"]))
    fact = evidence["facts"][0]
    move = evidence["discovery_defense_observation"]["defense"]["move"]
    result = snapshot(db, board, evidence, fact, marker, move)
    if source(db, int(key), subject) != evidence:
        raise ValueError("discovery defense changed")
    if source_marker(db, evidence["position_id"], evidence["game_id"], subject) != marker:
        raise ValueError("discovery defense changed")
    return result
