"""Identify valuable targets attacked by the moved piece after a legal fork move."""

from .fork_geometry import geometry


def targets(board, move):
    if not _eligible(board, move):
        return None
    return geometry(board, move)


def unsupported_shape(board, move):
    if move not in board.legal_moves:
        return False
    if not (board.is_capture(move) or move.promotion):
        return False
    return geometry(board, move) is not None


def _eligible(board, move):
    return (
        move in board.legal_moves
        and not board.is_capture(move)
        and not move.promotion
        and not board.is_check()
        and board.ep_square is None
        and not board.is_repetition(2)
        and not board.is_fifty_moves()
    )
