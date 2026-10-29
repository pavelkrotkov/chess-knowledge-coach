"""Validate each branch of a checking-capture proof."""

from .material_exchange_rules import unclear
from .material_lines import material


def eligible(board, move):
    return (
        move in board.legal_moves
        and board.is_capture(move)
        and board.gives_check(move)
        and not board.is_check()
        and board.ep_square is None
        and not board.is_en_passant(move)
        and not move.promotion
        and not board.is_repetition(2)
    )


def reply_value(board, reply, color, initial):
    if (
        board.is_capture(reply)
        or board.gives_check(reply)
        or reply.promotion
        or board.is_en_passant(reply)
    ):
        return None
    after = board.copy()
    after.push(reply)
    if unclear(after):
        return None
    return material(after, color) - initial
