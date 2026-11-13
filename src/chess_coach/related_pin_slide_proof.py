"""Verify only that a relative-pin slide blocks its named rear capture."""

import chess

from .material_exchange_rules import unclear
from .pin_existing import existing


def pin(board):
    candidates = existing(board)
    if len(candidates) != 1 or candidates[0][1]["type"] != "relative_pin":
        return None
    return candidates[0]


def slide(board, move, attacker, named):
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
        return False
    after = board.copy(stack=True)
    after.push(move)
    if after.is_game_over(claim_draw=True) or after.is_repetition(2):
        return False
    return not after.is_legal(chess.Move(attacker, named["rear"]))
