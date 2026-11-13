"""Recheck one owned recorded-choice material defense for a cued replay."""

from .decision_history import decision_board
from .discovery_material_contract import PRACTICE
from .discovery_material_practice_check import source
from .mate_inspection_source import position_row
from .material_source_marker import source_marker
from .objective_defense_freshness import review_id
from .objective_source_budget import within_budget


def resolve(db, version, key, subject):
    if not _valid_key(version, key):
        raise ValueError("discovery material practice unavailable")
    if not within_budget(db, int(key), subject):
        raise ValueError("discovery material practice unavailable")
    evidence = source(db, int(key), subject)
    marker = source_marker(db, evidence["position_id"], evidence["game_id"], subject)
    board = decision_board(db, position_row(db, evidence["position_id"]))
    fact = evidence["discovery_material_observation"]
    snapshot = {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": "legal_line",
        "lines": [fact["defense"]["move"]],
        "provenance": {
            "evidence_id": evidence["id"],
            "position_id": evidence["position_id"],
            "review_status": evidence["review_status"],
            "review_event_id": review_id(db, evidence["id"]),
            "detector_run_id": evidence["facts"][0]["detector_run_id"],
            "source_fingerprint": marker,
            "discovery_target": fact["target_origin"],
            "discovery_slider": fact["threat"]["slider"],
            "discovery_move": fact["threat"]["move"],
        },
    }
    if (
        source(db, int(key), subject) != evidence
        or source_marker(db, evidence["position_id"], evidence["game_id"], subject) != marker
    ):
        raise ValueError("discovery material source changed")
    return snapshot


def _valid_key(version, key):
    return version == PRACTICE and key.isdecimal() and 0 < int(key) < 2**63 and str(int(key)) == key
