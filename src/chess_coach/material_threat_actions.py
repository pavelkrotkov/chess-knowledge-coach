"""Classify candidate capture threats by the piece they target."""

import chess

from .material_check_proof import checking_capture
from .material_exchange import exchange
from .material_exchange_rules import has_legal_recapture


def collect(probe):
    targets = {}
    uncertain = {}
    for move in probe.generate_pseudo_legal_captures():
        target = probe.piece_at(move.to_square)
        if not _supported_target(target):
            continue
        value = _gain(probe, move)
        if value is None:
            uncertain.setdefault(move.to_square, []).append(move.uci())
        elif value >= 3:
            targets.setdefault(move.to_square, []).append(move.uci())
    return {"targets": targets, "uncertain": uncertain}


def _supported_target(target):
    return target is not None and target.piece_type not in {chess.PAWN, chess.KING}


def _gain(probe, move):
    if move not in probe.legal_moves:
        return None
    if probe.gives_check(move):
        proof = checking_capture(probe, move)
        return proof["minimum_gain"] if proof else None
    if has_legal_recapture(probe, move):
        return None
    return exchange(probe, move)
