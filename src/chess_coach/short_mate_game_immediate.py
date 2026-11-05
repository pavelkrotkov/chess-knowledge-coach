"""Check for immediate checkmate without claiming completion after a deadline."""


def immediate(board, moves, deadline, clock):
    for move in moves:
        if clock() >= deadline:
            return None
        board.push(move)
        try:
            mate = board.is_checkmate()
        finally:
            board.pop()
        if clock() >= deadline:
            return None
        if mate:
            return True
    return False
