"""Validate a direct target and bounded exchange gain."""

import chess

from .material_check_proof import checking_capture
from .material_exchange import VALUES, exchange
from .material_exchange_rules import has_legal_recapture

MIN_GAIN = 3


def capture_gain(board, candidate, target):
    if not _supported(target):
        return None, "special_capture", None
    if target.piece_type == chess.PAWN:
        return None, "pawn_capture_outside_coverage", None
    if board.gives_check(candidate):
        return _checking_gain(board, candidate)
    if candidate in board.legal_moves and has_legal_recapture(board, candidate):
        return None, "recapture_or_sacrifice", None
    gain = exchange(board, candidate)
    if gain is None:
        return None, "exchange_unresolved", None
    return (None, "recapture_or_sacrifice", None) if gain < MIN_GAIN else (gain, None, None)


def _checking_gain(board, candidate):
    proof = checking_capture(board, candidate)
    return (
        (proof["minimum_gain"], None, proof)
        if proof
        else (None, "checking_capture_unresolved", None)
    )


def _supported(target):
    return target is not None and target.piece_type in VALUES
