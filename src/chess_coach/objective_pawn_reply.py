"""Select one re-proved legal training reply within the shared proof budget."""

from . import pawn_proof
from .objective_pawn_bounds import alternative
from .objective_pawn_proof import inspect
from .objective_short_history import history_hash


def reply(board, move, goal, nodes, clock, start, seconds):
    after = board.copy(stack=True)
    after.push(move)
    remaining = pawn_proof.MAX_NODES - nodes
    if remaining < 1 or after.is_game_over(claim_draw=True):
        return {"status": "unavailable", "reason": "terminal_or_budget"}
    proof = inspect(after, node_limit=remaining)
    if clock() - start > seconds:
        return {"status": "unavailable", "reason": "timeout"}
    result = _choose(after, proof, goal)
    return {"status": "unavailable", "reason": "timeout"} if clock() - start > seconds else result


def _choose(board, proof, goal):
    for move in sorted(board.legal_moves, key=lambda item: item.uci()):
        interval = alternative(proof, move.uci())
        if interval is not None and interval[1] <= -goal:
            board.push(move)
            if board.is_game_over(claim_draw=True):
                board.pop()
                continue
            return {
                "status": "available",
                "reply": move.uci(),
                "opponent_bounds": list(interval),
                "fen": board.fen(),
                "history_hash": history_hash(board),
            }
    return {"status": "unavailable", "reason": "reply_not_proved"}
