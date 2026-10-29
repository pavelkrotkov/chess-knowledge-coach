"""Verify exactly an announced immediate or forced promotion objective."""

from .mate_proof import MAX_NODES
from .mate_proof_search import MAX_REPLIES
from .objective_capture_proof import unknown
from .objective_promotion_contract import NOW, VERIFIER
from .objective_promotion_root import evaluate
from .objective_promotion_scope import reason as scope_reason
from .objective_short_history import history_hash


def judge(board, move, objective, clock, start, seconds, base):
    reason = scope_reason(board, move, objective, clock, start, seconds)
    if reason:
        return unknown(base, reason)
    result = {
        **base,
        "verifier": VERIFIER,
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
        "limits": {
            "plies": 1 if objective == NOW else 3,
            "node_limit": MAX_NODES,
            "reply_limit": MAX_REPLIES,
            "compute_timeout_seconds": seconds,
        },
    }
    return evaluate(board, move, objective, clock, start, seconds, result)
