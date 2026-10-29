"""Select the bounded material observation appropriate to one decision."""

import chess

from .material_ambiguity import ambiguous
from .material_defense import defense_observation
from .material_observation_fallback import fallback_observation


def material_observation(board, played, best_line, played_line):
    try:
        actual = chess.Move.from_uci(played)
    except ValueError:
        return ambiguous("material_capture", "invalid_root")
    if actual not in board.legal_moves:
        return ambiguous("material_capture", "illegal_or_pinned_root")
    defense = defense_observation(board, played, best_line, played_line)
    if defense is not None and defense.get("outcome") == "success":
        return defense
    return fallback_observation(board, played, actual, best_line, played_line, defense)
