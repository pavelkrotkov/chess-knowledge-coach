"""Revalidate the restricted scout roots on purpose-result readback."""

from .purpose_early_center import roots
from .purpose_lines import roots as line_roots


def nominee(lines, board, position):
    allowed = {move.uci() for move in roots(board, position)}
    moves = line_roots(lines)
    ranks = [item["rank"] for item in lines]
    if not 1 <= len(moves) <= 2 or len(set(moves)) != len(moves):
        return None
    if not all(move in allowed for move in moves) or ranks not in ([1], [2], [1, 2]):
        return None
    return moves[0]
