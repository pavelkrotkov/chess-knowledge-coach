"""Identify bounded immediate-capture transfer patterns from legal lines."""

import chess

from .material_capture_gain import capture_gain
from .puzzle_session_validate import legal_move, validate_line
from .related_capture_position import _features, _supported_move


def _shape(prompt, line):
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
        return board, move, mover, target
    except (ValueError, TypeError, IndexError):
        return None


def certified_features(prompt, line):
    """Read geometry only after the owned source certificate was rechecked."""
    shape = _shape(prompt, line)
    return _features(*shape) if shape else None


def capture_features(prompt, line):
    """Return a supported immediate capture shape, or None for unsupported lines."""
    shape = _shape(prompt, line)
    if shape is None:
        return None
    board, move, mover, target = shape
    try:
        _, reason, _ = capture_gain(board, move, target)
        return None if reason else _features(board, move, mover, target)
    except (ValueError, TypeError, IndexError):
        return None


def corpus_features(fen, solution):
    """Replay the setup and full line before measuring the learner prompt."""
    try:
        prompt = validate_line(fen, solution)
        return prompt, capture_features(prompt, solution.split()[1:])
    except (ValueError, TypeError):
        return None, None
