"""Identify bounded immediate-capture transfer patterns from legal lines."""

import chess

from .material_capture_gain import capture_gain
from .puzzle_session_validate import legal_move, validate_line
from .related_capture_position import _features


def capture_features(prompt, line):
    """Return a supported immediate capture shape, or None for unsupported lines."""
    try:
        board = chess.Board(prompt)
        if not board.is_valid() or not line:
            return None
        replay = board.copy()
        for text in line:
            replay.push(legal_move(replay, text))
        move = legal_move(board, line[0])
        mover, target = board.piece_at(move.from_square), board.piece_at(move.to_square)
        if not _supported_move(board, move, mover, target):
            return None
        _, reason, _ = capture_gain(board, move, target)
        if reason:
            return None
        return _features(board, move, mover, target)
    except (ValueError, TypeError, IndexError):
        return None


def corpus_features(fen, solution):
    """Replay the setup and full line before measuring the learner prompt."""
    try:
        prompt = validate_line(fen, solution)
        return prompt, capture_features(prompt, solution.split()[1:])
    except (ValueError, TypeError):
        return None, None


def _supported_move(board, move, mover, target):
    return bool(
        mover
        and target
        and board.is_capture(move)
        and not board.gives_check(move)
        and not board.is_check()
        and not move.promotion
        and not board.is_en_passant(move)
    )
