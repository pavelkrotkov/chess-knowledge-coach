"""Legal roots for a scheduled early-center capture contrast."""

from .style_center_capture import capture
from .style_early_center import eligible


def _central(board, move):
    found = capture(board, move, 1)
    return bool(found and found["central"])


def roots(board, position):
    if not eligible(board, position["ply"]):
        raise ValueError("early-center contrast unavailable")
    played = board.parse_uci(position["uci"])
    category = _central(board, played)
    return [move for move in board.legal_moves if _central(board, move) != category]
