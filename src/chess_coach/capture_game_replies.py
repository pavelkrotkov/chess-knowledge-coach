"""Classify bounded legal replies for the game capture audit."""

from .material_exchange_rules import unclear
from .material_lines import material
from .material_reply_guard import MAX_REPLIES, MIN_GAIN


def _reply(board, move, color, initial):
    if board.gives_check(move) or move.promotion or board.is_en_passant(move):
        return "unknown"
    after = board.copy()
    after.push(move)
    if unclear(after):
        return "unknown"
    return "disproved" if material(after, color) - initial < MIN_GAIN else "proved"


def inspect(board, move):
    color = board.turn
    initial = material(board, color)
    after = board.copy()
    after.push(move)
    replies = list(after.legal_moves)
    if not replies or len(replies) > MAX_REPLIES:
        return "unknown"
    unknown = False
    for reply in replies:
        status = _reply(after, reply, color, initial)
        if status == "disproved":
            return status
        unknown |= status == "unknown"
    return "unknown" if unknown else "proved"
