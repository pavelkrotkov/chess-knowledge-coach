"""Check the announced fork using the qualified bounded proof kernel."""

import chess

from .fork_proof import MAX_REPLIES, fork_proof
from .objective_capture_proof import unknown
from .objective_short_history import history_hash


def judge(board, move, attacker, anchor, clock, start, seconds, base):
    if clock() - start > seconds:
        return unknown(base, "timeout")
    if not move or move not in board.legal_moves or move.from_square != attacker:
        return unknown(base, "named_attacker_or_move_unavailable")
    proof = fork_proof(board, move)
    if clock() - start > seconds:
        return unknown(base, "timeout")
    if not proof or chess.square_name(anchor) not in proof["targets"]:
        return unknown(base, "fork_or_consequence_unresolved")
    return {
        **base,
        "status": "correct",
        "reason": "named_fork_and_gain_proved",
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
        "proven_gain_floor": 3,
        "proof": proof,
        "limits": {"reply_limit": MAX_REPLIES, "compute_timeout_seconds": seconds},
    }
