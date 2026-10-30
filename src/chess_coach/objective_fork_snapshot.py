"""Bind the original fork certificate and its named training objective."""

import chess

from .fork_proof import fork_proof
from .material_opportunity_source import load_source
from .objective_contract import OWNED_HISTORY
from .objective_fork_contract import GOAL, OBJECTIVE


def snapshot(db, board, evidence, fact):
    original = fact["payload"]["proof"]
    move = board.parse_uci(original["move"])
    if fork_proof(board, move) != original:
        raise ValueError("fork certificate changed")
    anchor = _anchor(board, original["targets"])
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
            "fork_certificate": original,
            "objective_version": OBJECTIVE,
            "history_mode": OWNED_HISTORY,
            "fork_attacker": chess.square_name(move.from_square),
            "fork_anchor": anchor,
            "gain_threshold": 3,
            "source_outcome": evidence["outcome"],
        },
    }


def _anchor(board, targets):
    kings = [
        square
        for square in targets
        if board.piece_at(chess.parse_square(square)).piece_type == chess.KING
    ]
    return kings[0] if kings else targets[0]
