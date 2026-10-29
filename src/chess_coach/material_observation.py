"""Select the bounded material observation appropriate to one decision."""

import chess

from .material_ambiguity import ambiguous
from .material_capture import capture_observation
from .material_defense import defense_observation
from .material_unavailable import without_best


def material_observation(board, played, best_line, played_line):
    if not isinstance(best_line, dict) or not isinstance(best_line.get("root_move"), str):
        return without_best(board, played, best_line, played_line)
    try:
        best = chess.Move.from_uci(best_line["root_move"])
        actual = chess.Move.from_uci(played)
    except ValueError:
        return ambiguous("material_capture", "invalid_root")
    if best not in board.legal_moves or actual not in board.legal_moves:
        return ambiguous("material_capture", "illegal_or_pinned_root")
    candidate = _candidate(board, best, actual)
    if candidate is False:
        return ambiguous("material_capture", "alternate_capture_or_sacrifice")
    if candidate is None:
        return defense_observation(board, played, best_line, played_line)
    return capture_observation(board, candidate, actual, best_line, played_line)


def _candidate(board, best, actual):
    if board.is_capture(best):
        return False if actual != best and board.is_capture(actual) else best
    return actual if board.is_capture(actual) else None
