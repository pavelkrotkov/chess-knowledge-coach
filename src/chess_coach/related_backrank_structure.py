"""Describe actual back-rank checkers and individual king escape squares."""

import chess


def describe(board, motif, attacker, tracked, promoted):
    king = chess.parse_square(motif["king"])
    checkers = {chess.parse_square(square) for square in motif["checkers"]}
    blocked = {chess.parse_square(square) for square in motif["occupied_flights"]}
    return {
        "opening_piece_survives": tracked is not None,
        "opening_piece_promoted": promoted,
        "opening_piece_checks": tracked is not None and tracked in board.checkers(),
        "opening_piece_backrank_checks": tracked in checkers,
        "backrank_checkers": tuple(
            sorted(_checker(board, king, square, attacker) for square in checkers)
        ),
        "escapes": tuple(
            sorted(
                (
                    _offset(king, square, attacker),
                    square in blocked,
                    board.is_attacked_by(attacker, square),
                )
                for square in chess.SquareSet(chess.BB_KING_ATTACKS[king])
            )
        ),
    }


def _checker(board, king, square, attacker):
    return board.piece_type_at(square), _offset(king, square, attacker)


def _offset(king, square, attacker):
    direction = 1 if attacker == chess.WHITE else -1
    return (
        chess.square_file(square) - chess.square_file(king),
        direction * (chess.square_rank(square) - chess.square_rank(king)),
    )
