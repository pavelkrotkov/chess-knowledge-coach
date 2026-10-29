"""Check whether any legal next reply checkmates the defender."""

from .back_rank_scan import MAX_MOVES
from .objective_defense_scan import MAX_NODES, after_move
from .objective_judge import _scope_reason
from .objective_short_history import history_hash

VERSION = "immediate-mate-defense-verifier-v1"


def judge(board, move, clock, start, seconds, base):
    if board.is_game_over(claim_draw=True):
        return {**base, "status": "unresolved", "reason": "terminal_or_claimable_history"}
    if not move or move not in board.legal_moves:
        return {**base, "status": "unresolved", "reason": "illegal_move"}
    result = {
        **base,
        "verifier": VERSION,
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
        "limits": {
            "plies": 2,
            "node_limit": MAX_NODES,
            "reply_limit": MAX_MOVES,
            "compute_timeout_seconds": seconds,
        },
    }
    board.push(move)
    try:
        return after_move(board, clock, start, seconds, result)
    finally:
        board.pop()


def verify(board, move, request, events, clock, start, seconds, base):
    reason = _scope_reason(board, request, events)
    if reason:
        return {**base, "status": "unresolved", "reason": reason}
    return judge(board, move, clock, start, seconds, base)
