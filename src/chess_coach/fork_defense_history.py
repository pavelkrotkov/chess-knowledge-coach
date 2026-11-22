"""Shared history boundary for positional and legal fork scans."""


def unsupported(board):
    return (
        board.is_check()
        or board.ep_square is not None
        or board.is_repetition(2)
        or board.is_fifty_moves()
        or board.is_game_over()
    )


def quiet_after(board, move):
    if board.is_capture(move) or board.gives_check(move) or move.promotion:
        return None
    after = board.copy()
    after.push(move)
    if after.ep_square is not None or after.is_repetition(2) or after.is_fifty_moves():
        return None
    return after
