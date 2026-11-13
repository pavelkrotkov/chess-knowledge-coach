"""Find a bounded independently proved exposure for a slide exercise."""

import chess

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_pin_prevent_existing import _matches
from .pin_exposure_geometry import exposed
from .related_pin_budget import take
from .related_pin_prevent_shape import features
from .related_pin_slide_proof import pin


def witness(board, good, named, moves, budget):
    attacker, pinned = named
    ray = chess.between(attacker, pinned["rear"])
    for bad in moves:
        if bad.from_square != pinned["pinned"] or chess.BB_SQUARES[bad.to_square] & ray:
            continue
        if not take(budget, "root_proofs"):
            return None
        proof = exposed(board, bad, [named])
        if proof:
            return (
                {**features(board, good, attacker, pinned), "origin": "slide"},
                proof,
                {"move": good.uci(), "san": board.san(good), "counterfactual": bad.uci()},
            )
    return None


def checked(db, source, bound):
    board = decision_board(db, position_row(db, source["provenance"]["position_id"]))
    named = pin(board)
    if board.fen() != source["prompt_fen"] or named is None or not _matches(named, bound):
        raise ValueError("named pin source changed")
    bad = board.parse_uci(bound["bad"])
    if bad not in board.legal_moves:
        raise ValueError("named exposure unavailable")
    if exposed(board, bad, [named]) != source["provenance"]["pin_witness"]:
        raise ValueError("named exposure changed")
    return board, named, bad
