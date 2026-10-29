"""Validate the board and each replayed continuation move."""


def valid_start(board):
    return not board.is_check() and board.ep_square is None and not board.is_repetition(2)


def valid_step(board, move, *, allow_checks=False):
    return (
        move in board.legal_moves
        and not move.promotion
        and not board.is_en_passant(move)
        and (allow_checks or not board.gives_check(move))
    )


def valid_end(board):
    return not board.is_game_over() and not board.is_repetition(2) and not board.is_fifty_moves()
