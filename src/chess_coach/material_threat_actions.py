"""Classify candidate capture threats in a validated hypothetical position."""

import chess

from .material_exchange import exchange
from .material_exchange_rules import has_legal_recapture


def collect(probe):
    targets = {}
    ambiguous = any(
        not probe.is_capture(move) and probe.gives_check(move) for move in probe.legal_moves
    )
    for move in probe.generate_pseudo_legal_captures():
        target = probe.piece_at(move.to_square)
        if not _supported_target(target):
            continue
        value = _gain(probe, move)
        if value is None:
            ambiguous = True
        elif value >= 3:
            targets.setdefault(move.to_square, []).append(move.uci())
    return {"targets": targets, "ambiguous": ambiguous}


def _supported_target(target):
    return target is not None and target.piece_type not in {chess.PAWN, chess.KING}


def _gain(probe, move):
    if move not in probe.legal_moves or has_legal_recapture(probe, move):
        return None
    return exchange(probe, move)
