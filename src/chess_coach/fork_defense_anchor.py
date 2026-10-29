"""Prove a positional threat after a legal learner move with real history."""

from .fork_defense_anchor_match import find_fork
from .fork_defense_safety import quiet_after, safe_material

MAX_ANCHOR_MOVES = 64
MAX_PROOFS = 32


def anchor(board, candidates):
    moves = list(board.legal_moves)
    if len(moves) > MAX_ANCHOR_MOVES:
        return {"reason": "anchor_move_budget_exhausted"}
    budget = MAX_PROOFS
    for move in moves:
        after = quiet_after(board, move)
        if after is None or not safe_material(after):
            continue
        proof, budget = find_fork(after, candidates, budget)
        if proof:
            return {"move": move.uci(), "san": board.san(move), "fork": proof}
        if budget < 0:
            return {"reason": "anchor_proof_budget_exhausted"}
    return None
