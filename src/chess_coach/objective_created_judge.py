"""Check one named piece against bounded immediate material captures."""

import chess

from .objective_capture_scope import reason as scope_reason
from .objective_created_result import classify
from .objective_protection_after import unknown
from .objective_short_history import history_hash
from .pawn_scope import history_known

CAPTURES = 64


class CaptureLimit(Exception):
    """A complete bounded scan was unavailable."""


def judge(board, move, target, clock, start, seconds, base):
    reason = _reason(board, move, target, clock, start, seconds)
    if reason:
        return unknown(base, reason)

    # A partial capture scan cannot establish the named piece is safe.
    def check(index):
        if index >= CAPTURES:
            raise CaptureLimit
        if clock() - start > seconds:
            raise TimeoutError

    try:
        result = classify(board, move, target, check)
        check(0)
    except TimeoutError:
        return unknown(base, "timeout")
    except CaptureLimit:
        return unknown(base, "capture_limit")
    return {
        **base,
        **result,
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
    }


def _reason(board, move, target, clock, start, seconds):
    reason = scope_reason(board, move, clock, start, seconds)
    if reason:
        return reason
    if board.is_capture(move) or not history_known(board):
        return "move_or_history_unresolved"
    piece = board.piece_at(target)
    if piece is None or piece.color != board.turn or piece.piece_type in {chess.PAWN, chess.KING}:
        return "named_piece_unavailable"
    return None
