"""Describe a legal supplied mating line without asserting a forced mate."""

import chess

from .puzzle_session_validate import legal_move, validate_line
from .related_mate_shape import features


def mate_features(prompt, line):
    try:
        board = chess.Board(prompt)
        if not board.is_valid() or len(line) not in (1, 3):
            return None
        root = board.copy(stack=True)
        first = legal_move(board, line[0])
        mover = _piece_type(board, first)
        for text in line[:-1]:
            board.push(legal_move(board, text))
            if board.is_game_over():
                return None
        final = legal_move(board, line[-1])
        board.push(final)
        if not board.is_checkmate():
            return None
        return features(root, board, mover, len(line))
    except (ValueError, TypeError, AttributeError, IndexError):
        return None


def _piece_type(board, move):
    piece = board.piece_at(move.from_square)
    if piece is None:
        raise ValueError("missing attacker")
    return piece.piece_type


def corpus_features(fen, solution):
    try:
        prompt = validate_line(fen, solution)
        return prompt, mate_features(prompt, solution.split()[1:])
    except (ValueError, TypeError):
        return None, None
