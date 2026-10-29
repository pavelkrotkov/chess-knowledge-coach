"""Describe a legal rook or queen checkmate on the king's home rank."""

import chess


def terminal(board):
    if not board.is_checkmate():
        return None
    king = board.king(board.turn)
    rank = 0 if board.turn == chess.WHITE else 7
    if king is None or chess.square_rank(king) != rank:
        return None
    checkers = _checkers(board, rank)
    if not checkers:
        return None
    return {
        "king": chess.square_name(king),
        "checkers": checkers,
        "occupied_flights": _blocked(board, king),
    }


def _checkers(board, rank):
    return [
        chess.square_name(square)
        for square in board.checkers()
        if chess.square_rank(square) == rank
        and board.piece_type_at(square) in (chess.ROOK, chess.QUEEN)
    ]


def _blocked(board, king):
    return [
        chess.square_name(square)
        for square in chess.SquareSet(chess.BB_KING_ATTACKS[king])
        if (piece := board.piece_at(square)) is not None and piece.color == board.turn
    ]
