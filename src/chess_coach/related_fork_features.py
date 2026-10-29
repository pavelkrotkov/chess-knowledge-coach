"""Recognize a first-move pawn or knight fork in a complete supplied line."""

import chess

from .fork_targets import targets
from .puzzle_session_validate import legal_move, validate_line
from .related_fork_consequence import target_captured
from .related_fork_geometry import features


def fork_features(prompt, line):
    """Return fork structure only if the line captures an original target next."""
    try:
        board = chess.Board(prompt)
        if not board.is_valid() or not 3 <= len(line) <= 64:
            return None
        replay = board.copy()
        for text in line:
            replay.push(legal_move(replay, text))
        first = legal_move(board, line[0])
        piece = board.piece_at(first.from_square)
        shape = targets(board, first)
        if not _supported(piece, shape):
            return None
        if not target_captured(board, first, shape[1], line):
            return None
        return features(board, first, piece, shape[1])
    except (ValueError, TypeError, IndexError):
        return None


def corpus_fork_features(fen, solution):
    try:
        prompt = validate_line(fen, solution)
        return prompt, fork_features(prompt, solution.split()[1:])
    except (ValueError, TypeError):
        return None, None


def _supported(piece, shape):
    return bool(piece and piece.piece_type in {chess.PAWN, chess.KNIGHT} and shape)
