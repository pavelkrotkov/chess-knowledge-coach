"""Bounded legal one-move mate scans, preserving the board's history."""

from .back_rank_terminal import terminal
from .mate_proof_moves import move_view

MAX_MOVES = 100


def mate_scan(board, budget):
    moves = sorted(board.legal_moves, key=lambda move: move.uci())
    if len(moves) > MAX_MOVES:
        return {"status": "unknown", "reason": "reply_limit"}
    back_rank, other = [], []
    for move in moves:
        if not budget.visit():
            return {"status": "unknown", "reason": "node_limit"}
        view = move_view(board, move)
        board.push(move)
        if board.is_checkmate():
            geometry = terminal(board)
            if geometry:
                back_rank.append({"move": view, "geometry": geometry})
            else:
                other.append(view)
        board.pop()
    return {"status": "complete", "back_rank": back_rank, "other_mates": other}
