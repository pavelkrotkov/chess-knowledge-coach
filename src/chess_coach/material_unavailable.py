"""Retain ambiguity when no current best continuation is available."""

import chess

from .material_ambiguity import ambiguous
from .material_defense import defense_observation


def without_best(board, played, best_line, played_line):
    for move in board.legal_moves:
        target = board.piece_at(move.to_square)
        if board.is_capture(move) and target and target.piece_type not in {chess.PAWN, chess.KING}:
            return ambiguous("material_capture", "current_analysis_unavailable")
    return defense_observation(board, played, best_line, played_line)
