"""Independently verify one specified-piece defense."""

from .material_defense_safety import safe_defense_move
from .material_reply_guard import MAX_REPLIES
from .objective_capture_scope import reason as scope_reason
from .objective_protection_after import assess, unknown
from .objective_protection_before import probe
from .objective_protection_piece import same_piece
from .objective_short_history import history_hash

VERSION = "threatened-piece-verifier-v1"


def judge(board, move, target, clock, start, seconds, base):
    reason = scope_reason(board, move, clock, start, seconds)
    if reason:
        return unknown(base, reason)
    before = probe(board)
    if before is None or set(before["targets"]) != {target}:
        return unknown(base, "original_threat_unresolved")
    if not safe_defense_move(board, move, before):
        return unknown(base, "defense_move_unresolved")
    original = board.piece_at(target)
    square = move.to_square if move.from_square == target else target
    result = {
        **base,
        "verifier": VERSION,
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
        "limits": {"plies": 3, "reply_limit": MAX_REPLIES, "compute_timeout_seconds": seconds},
    }
    after = board.copy(stack=True)
    after.push(move)
    if not same_piece(board, after, original, square):
        return unknown(result, "protected_piece_unavailable")
    return assess(after, square, before, clock, start, seconds, result)
