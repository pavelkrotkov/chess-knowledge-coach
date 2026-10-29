"""Bounded legal proof of mate in at most two moves, with complete defenses."""

from .mate_proof_moves import Budget as Budget
from .mate_proof_moves import immediate_mates as immediate_mates
from .mate_proof_moves import move_view
from .mate_proof_search import MAX_REPLIES, _defenses

VERSION = "mate-proof-v1"
MAX_NODES = 6000


def _root(board, move, budget):
    if not budget.visit():
        return {"move": move_view(board, move), "status": "unknown"}
    view = move_view(board, move)
    board.push(move)
    if board.is_checkmate():
        result = {"move": view, "status": "proved", "distance_plies": 1, "defenses": []}
    else:
        status, defenses = _defenses(board, budget)
        result = {
            "move": view,
            "status": status,
            "distance_plies": 3 if status == "proved" else None,
            "defenses": defenses,
        }
    board.pop()
    return result


def prove_short_mates(board, *, node_limit=MAX_NODES):
    """Search all root moves; a proved root includes a mate for every defense."""
    if not 1 <= node_limit <= MAX_NODES:
        raise ValueError("invalid proof node limit")
    budget = Budget(node_limit)
    direct = {item["uci"]: item for item in immediate_mates(board)}
    roots = [
        _known_or_search(board, move, direct, budget)
        for move in sorted(board.legal_moves, key=lambda m: m.uci())
    ]
    statuses = {root["status"] for root in roots}
    status = (
        "proved" if "proved" in statuses else "unknown" if "unknown" in statuses else "disproved"
    )
    return {
        "version": VERSION,
        "status": status,
        "max_plies": 3,
        "node_limit": node_limit,
        "nodes": budget.nodes,
        "reply_limit": MAX_REPLIES,
        "alternatives": roots,
    }


def _known_or_search(board, move, direct, budget):
    if move.uci() in direct:
        return {"move": direct[move.uci()], "status": "proved", "distance_plies": 1, "defenses": []}
    return _root(board, move, budget)
