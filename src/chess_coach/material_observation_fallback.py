"""Select capture or unresolved evidence when no played defense was proven."""

import chess

from .material_ambiguity import ambiguous
from .material_capture import capture_observation
from .material_unavailable import without_best


def fallback_observation(board, played, actual, best_line, played_line, defense):
    if board.is_capture(actual):
        return capture_observation(board, actual, actual, best_line, played_line)
    best = _best_move(board, best_line)
    if best is False:
        return ambiguous("material_capture", "illegal_or_pinned_root")
    if best is None:
        return defense or without_best(board, played, best_line, played_line)
    if board.is_capture(best):
        return capture_observation(board, best, actual, best_line, played_line)
    return defense


def _best_move(board, best_line):
    if not isinstance(best_line, dict) or not isinstance(best_line.get("root_move"), str):
        return None
    try:
        best = chess.Move.from_uci(best_line["root_move"])
    except ValueError:
        return False
    return best if best in board.legal_moves else False
