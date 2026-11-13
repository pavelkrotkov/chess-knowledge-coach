"""Verify only that a relative-pin slide blocks its named rear capture."""

import chess

from .material_exchange_rules import unclear
from .pin_existing import existing


def pin(board, kind=None):
    candidates = existing(board)
    if len(candidates) != 1 or (kind is not None and candidates[0][1]["type"] != kind):
        return None
    return candidates[0]


def slide_proof(board, move, attacker, named):
    if any(
        (
            unclear(board),
            board.ep_square is not None,
            move not in board.legal_moves,
            board.is_capture(move),
            move.promotion,
            move.from_square != named["pinned"],
            not chess.between(attacker, named["rear"]) & chess.BB_SQUARES[move.to_square],
        )
    ):
        return None
    after = board.copy(stack=True)
    after.push(move)
    if after.is_game_over(claim_draw=True) or after.is_repetition(2):
        return None
    if named["type"] == "relative_pin":
        return {} if not after.is_legal(chess.Move(attacker, named["rear"])) else None
    if named["type"] == "absolute_pin":
        from .related_pin_absolute_slide import refutation

        return refutation(after, move, attacker)
    return None


def slide(board, move, attacker, named):
    return slide_proof(board, move, attacker, named) is not None
