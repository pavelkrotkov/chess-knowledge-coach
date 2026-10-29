"""Check the last mating ply without searching a longer horizon."""

from .mate_proof import VERSION
from .mate_proof_moves import move_view
from .objective_short_history import history_hash


def judge(board, move, clock, start, seconds, base):
    result = {
        **base,
        "history_hash": history_hash(board),
        "proof_version": VERSION,
        "limits": {"plies": 1, "nodes": 1, "node_limit": 1, "compute_timeout_seconds": seconds},
    }
    if clock() - start > seconds:
        return {**result, "status": "unresolved", "reason": "timeout"}
    view = move_view(board, move)
    board.push(move)
    mate = board.is_checkmate()
    board.pop()
    if clock() - start > seconds:
        return {**result, "status": "unresolved", "reason": "timeout"}
    if not mate:
        return {**result, "status": "incorrect", "reason": "not_mate_within_horizon"}
    proof = {"move": view, "status": "proved", "distance_plies": 1, "defenses": []}
    return {**result, "status": "correct", "reason": "immediate_checkmate", "proof": proof}
