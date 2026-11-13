"""Reject unknown historical and unsupported discovery-success roots."""

from .discovery_branch import unclear
from .pawn_scope import history_known


def unsupported(board):
    return (
        not board.is_valid()
        or not history_known(board)
        or board.is_check()
        or board.ep_square is not None
        or unclear(board)
        or board.is_fifty_moves()
    )


def unclear_after(board, move):
    after = board.copy()
    after.push(move)
    return unclear(after)
