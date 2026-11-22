"""Enumerate legal and positional fork candidates under a cooperative check."""

from .fork_geometry import _valuable
from .fork_targets import targets, unsupported_shape


def legal_candidates(board, moves, check):
    candidates = []
    for move in moves:
        check()
        if targets(board, move) is not None or unsupported_shape(board, move):
            candidates.append(move)
    return candidates


def positional_candidates(board, moves, check):
    result = {}
    for move in moves:
        check()
        squares = _targets(board, move)
        if len(squares) >= 2:
            result[move.uci()] = squares
    return result


def _targets(board, move):
    if board.is_capture(move) or move.promotion:
        return []
    after = board.copy(stack=False)
    after.push(move)
    return sorted(
        square
        for square in after.attacks(move.to_square)
        if _valuable(after.piece_at(square), board.turn)
    )
