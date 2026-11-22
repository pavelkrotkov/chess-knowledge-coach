"""Identify positions outside the existing fork kernel before enumeration."""


def supported(board):
    return not (
        board.is_check()
        or board.ep_square is not None
        or board.is_repetition(2)
        or board.is_fifty_moves()
    )
