"""Prove a named quiet relative-pin slide and every immediate front capture."""

import chess

from .objective_pin_slide_budget import take
from .objective_pin_slide_exchange import recapture
from .objective_pin_slide_scope import _quiet, named_pin, replies_supported
from .related_pin_slide_proof import slide_proof


def prove(board, move, named):
    if not _quiet(board, move):
        return None
    if move.from_square != chess.parse_square(named["pinned"]):
        return None
    candidate = named_pin(board, named)
    if candidate is None or slide_proof(board, move, *candidate) is None:
        return None
    after = board.copy(stack=True)
    after.push(move)
    replies = list(after.legal_moves)
    take(len(replies) + 1)
    if not replies_supported(after, replies, move.to_square):
        return None
    attacks = [reply for reply in replies if after.is_capture(reply)]
    return _witnesses(after, attacks, move.to_square)


def _witnesses(board, attacks, target):
    if not attacks:
        return None
    witnesses = []
    for attack in sorted(attacks, key=lambda item: item.uci()):
        witness = recapture(board, attack, target)
        if witness is None:
            return None
        witnesses.append(witness)
    return witnesses
