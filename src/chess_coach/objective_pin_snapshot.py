"""Bind the original bounded pin certificate and its named identities."""

import chess

from .material_opportunity_source import load_source
from .objective_contract import OWNED_HISTORY
from .objective_pin_contract import GOAL, OBJECTIVE
from .pin_proof import proven


def snapshot(db, board, evidence, fact):
    original = fact["payload"]["proof"]
    move = board.parse_uci(original["move"])
    if original not in proven(board, move):
        raise ValueError("pin certificate changed")
    reviews = evidence["reviews"]
    source = load_source(db, fact["detector_run_id"])
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": GOAL,
        "lines": [move.uci()],
        "provenance": {
            "source_fingerprint": source["source_marker"],
            "evidence_id": evidence["id"],
            "position_id": evidence["position_id"],
            "review_status": evidence["review_status"],
            "review_event_id": reviews[-1]["id"] if reviews else None,
            "mapping_run_id": evidence["mapping_run_id"],
            "mapper_version": evidence["mapper_version"],
            "fact_id": fact["id"],
            "detector_run_id": fact["detector_run_id"],
            "pin_certificate": original,
            "objective_version": OBJECTIVE,
            "history_mode": OWNED_HISTORY,
            "pin_attacker": chess.square_name(move.from_square),
            "pin_pinned": original["pinned"],
            "pin_rear": original["rear"],
            "pin_type": original["type"],
            "source_outcome": evidence["outcome"],
        },
    }
