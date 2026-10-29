"""Verify bounded back-rank mating witnesses after every legal defense."""

from .back_rank_attack_replies import defenses
from .back_rank_candidate import unknown
from .back_rank_scan import MAX_MOVES
from .back_rank_terminal import terminal
from .mate_proof_moves import Budget

VERSION = "back-rank-attack-v1"
MAX_NODES = 6000


def prove(board, mate_proof, *, node_limit=MAX_NODES):
    if not 1 <= node_limit <= MAX_NODES:
        raise ValueError("invalid back-rank proof budget")
    budget = Budget(node_limit)
    candidates = [
        root for root in mate_proof.get("alternatives", []) if root.get("status") == "proved"
    ]
    roots = [_root(board, candidate, budget) for candidate in candidates]
    return {
        "version": VERSION,
        "node_limit": node_limit,
        "reply_limit": MAX_MOVES,
        "nodes": budget.nodes,
        "alternatives": roots,
        "status": "unknown" if unknown(mate_proof, roots) else "complete",
    }


def _root(board, candidate, budget):
    text = candidate["move"]["uci"]
    try:
        move = board.parse_uci(text)
    except ValueError:
        return {"move": candidate["move"], "status": "unknown", "reason": "invalid_move"}
    if not budget.visit():
        return {"move": candidate["move"], "status": "unknown", "reason": "node_limit"}
    board.push(move)
    try:
        geometry = terminal(board)
        if geometry:
            return {
                "move": candidate["move"],
                "status": "proved",
                "distance_plies": 1,
                "geometry": geometry,
                "defenses": [],
            }
        if board.outcome(claim_draw=False) or board.can_claim_draw():
            return {"move": candidate["move"], "status": "disproved"}
        return defenses(board, candidate, budget)
    finally:
        board.pop()
