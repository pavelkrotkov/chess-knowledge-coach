"""Bounded immediate material proof over every legal reply to a checking capture."""

from .material_check_rules import eligible, reply_value
from .material_lines import material

MAX_CHECK_REPLIES = 64


def checking_capture(board, move):
    if not eligible(board, move):
        return None
    color = board.turn
    initial = material(board, color)
    after = board.copy()
    after.push(move)
    if _terminal(after):
        return None
    replies = list(after.legal_moves)
    if not replies or len(replies) > MAX_CHECK_REPLIES:
        return None
    values = []
    for reply in replies:
        value = reply_value(after, reply, color, initial)
        if value is None:
            return None
        values.append(value)
    gain = min(values)
    return {"minimum_gain": gain, "legal_replies": len(replies)} if gain >= 3 else None


def _terminal(board):
    return board.is_game_over() or board.is_repetition(2) or board.is_fifty_moves()
