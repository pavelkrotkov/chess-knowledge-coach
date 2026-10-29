"""Reject a material claim when an immediate legal reply can erase its gain."""

from .material_exchange_rules import unclear
from .material_lines import material

MAX_REPLIES = 64
MIN_GAIN = 3


def unresolved_reply(board, move):
    color = board.turn
    initial = material(board, color)
    after = board.copy()
    after.push(move)
    replies = list(after.legal_moves)
    if not replies or len(replies) > MAX_REPLIES:
        return True
    return any(_unresolved(after, reply, color, initial) for reply in replies)


def _unresolved(board, move, color, initial):
    if board.gives_check(move) or move.promotion or board.is_en_passant(move):
        return True
    after = board.copy()
    after.push(move)
    if unclear(after):
        return True
    return board.is_capture(move) and material(after, color) - initial < MIN_GAIN
