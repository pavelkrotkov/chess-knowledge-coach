"""Render bounded WDL and legal alternative results from the mover perspective."""

from .mate_proof_moves import move_view
from .pawn_outcome_search import Budget, bounds


def _alternative(board, move, tablebase, budget, depth):
    view = move_view(board, move)
    board.push(move)
    low, high, reason = bounds(board, tablebase, budget, depth - 1)
    board.pop()
    return {"move": view, "lower": -high, "upper": -low, "reason": reason}


def report(board, tablebase, node_limit, max_plies):
    budget = Budget(node_limit)
    low, high, reason = bounds(board, tablebase, budget, max_plies)
    moves = (
        []
        if board.outcome(claim_draw=False)
        else sorted(board.legal_moves, key=lambda m: (not board.is_zeroing(m), m.uci()))
    )
    alternatives = [_alternative(board, move, tablebase, budget, max_plies) for move in moves]
    return {
        "status": "complete" if low == high else "unknown",
        "lower": low,
        "upper": high,
        "reason": reason,
        "alternatives": alternatives,
        "native_wdl_counts": budget.native_wdl,
        "nodes": budget.nodes,
        "node_limit": node_limit,
        "max_plies": max_plies,
        "claim_available": board.can_claim_draw(),
        "claim_policy": "either player may claim when legal; optimal play",
    }
