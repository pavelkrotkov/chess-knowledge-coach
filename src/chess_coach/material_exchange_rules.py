"""Reject exchange branches requiring unsupported chess semantics."""


def ordinary_capture(board, move):
    return (
        move in board.legal_moves
        and board.is_capture(move)
        and not board.is_en_passant(move)
        and move.promotion is None
        and not board.is_check()
        and not board.gives_check(move)
        and board.ep_square is None
    )


def unclear(board):
    return (
        board.is_check() or board.is_game_over() or board.is_repetition(2) or board.is_fifty_moves()
    )


MAX_EXCHANGE_NODES = 64
MAX_EXCHANGE_PLIES = 6


def over_limit(board, budget, depth):
    return budget[0] > MAX_EXCHANGE_NODES or depth > MAX_EXCHANGE_PLIES or unclear(board)


def captures(board, square):
    return [
        move for move in board.legal_moves if move.to_square == square and board.is_capture(move)
    ]


def has_legal_recapture(board, move):
    after = board.copy()
    after.push(move)
    return any(
        reply.to_square == move.to_square and after.is_capture(reply) for reply in after.legal_moves
    )
