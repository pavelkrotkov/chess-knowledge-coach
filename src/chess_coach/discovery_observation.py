"""Compare legal roots without inferring skill from a search score."""

import chess

from .discovery_compare import compare as _compare
from .discovery_compare import unresolved as _unresolved
from .discovery_line import lines as _lines
from .material_observation_fallback import _best_move


def observe(board, played, best_line, played_line):
    try:
        actual = chess.Move.from_uci(played)
    except (TypeError, ValueError):
        return None
    if (
        not board.is_valid()
        or board.is_game_over(claim_draw=True)
        or actual not in board.legal_moves
    ):
        return None
    best = _best_move(board, best_line)
    if not isinstance(best, chess.Move):
        return _unresolved(board, actual, None, "best_root_unavailable")
    lines = _lines(board, best, actual, best_line, played_line)
    if lines is None:
        return _unresolved(board, actual, best, "comparable_lines_unavailable")
    return _compare(board, actual, best, lines)
