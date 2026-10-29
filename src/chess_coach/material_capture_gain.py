"""Validate a direct target and bounded exchange gain."""

import chess

from .material_exchange import VALUES, exchange
from .material_exchange_rules import has_legal_recapture

MIN_GAIN = 3


def capture_gain(board, candidate, target):
    if target is None or target.piece_type not in VALUES:
        return None, "special_capture"
    if target.piece_type == chess.PAWN:
        return None, "pawn_capture_outside_coverage"
    if candidate in board.legal_moves and has_legal_recapture(board, candidate):
        return None, "recapture_or_sacrifice"
    gain = exchange(board, candidate)
    if gain is None:
        return None, "exchange_unresolved"
    return (None, "recapture_or_sacrifice") if gain < MIN_GAIN else (gain, None)
