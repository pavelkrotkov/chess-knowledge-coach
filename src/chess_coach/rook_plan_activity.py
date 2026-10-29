"""Describe rook attack geometry without claiming legal moves or recaptures."""

import chess


def activity(board, color):
    attacks = chess.SquareSet()
    for square in board.pieces(chess.ROOK, color):
        attacks |= board.attacks(square)
    enemy_half = chess.BB_RANK_5 | chess.BB_RANK_6 | chess.BB_RANK_7 | chess.BB_RANK_8
    if color == chess.BLACK:
        enemy_half = chess.BB_RANK_1 | chess.BB_RANK_2 | chess.BB_RANK_3 | chess.BB_RANK_4
    return [chess.square_name(square) for square in attacks & enemy_half]
