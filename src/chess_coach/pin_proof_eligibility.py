"""Check that the pin is a new, supported capture opportunity."""


def eligible(board, move):
    return not (
        board.is_check()
        or board.ep_square is not None
        or board.gives_check(move)
        or board.is_capture(move)
        or move.promotion
    )


def previous_capture(board, pin):
    return any(
        board.is_capture(move) and move.to_square in {pin["pinned"], pin["rear"]}
        for move in board.legal_moves
    )
