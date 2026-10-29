"""List every legal evasion of a conditional checking move within a budget."""

import chess

from .king_safety_scan import MAX_MOVES
from .mate_proof_moves import move_view


def evasions(board):
    moves = sorted(board.legal_moves, key=lambda move: move.uci())
    if len(moves) > MAX_MOVES:
        return {"status": "budget_exceeded", "count": None, "moves": []}
    return {
        "status": "complete",
        "count": len(moves),
        "moves": [
            {
                **move_view(board, move),
                "king_move": board.piece_type_at(move.from_square) == chess.KING,
                "capture": board.is_capture(move),
            }
            for move in moves
        ],
    }
