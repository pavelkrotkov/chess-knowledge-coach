"""Bound material claims to supported legal immediate replies."""

from .material_capture_gain import capture_gain
from .material_reply_guard import unresolved_reply


def capture(board, move, objective, target, threshold, clock, start, seconds, base):
    captures = board.is_capture(move) and not board.is_en_passant(move)
    if objective == "capture_named_target" and (not captures or move.to_square != target):
        return {**base, "status": "incorrect", "reason": "named_target_not_captured"}
    if not captures:
        return unknown(base, "other_move_unresolved")
    return _proof(board, move, threshold, clock, start, seconds, base)


def _proof(board, move, threshold, clock, start, seconds, base):
    gain, reason, _ = capture_gain(board, move, board.piece_at(move.to_square))
    if reason or unresolved_reply(board, move):
        return unknown(base, reason or "reply_or_compensation_unresolved")
    if clock() - start > seconds:
        return unknown(base, "timeout")
    if gain < threshold:
        return unknown(base, "gain_below_bound")
    after = board.copy(stack=True)
    after.push(move)
    return {
        **base,
        "status": "correct",
        "reason": "bounded_capture_proved",
        "proven_gain_floor": threshold,
        "exchange_gain": gain,
        "legal_replies": sorted(m.uci() for m in after.legal_moves),
    }


def unknown(base, reason):
    return {**base, "status": "unresolved", "reason": reason}
