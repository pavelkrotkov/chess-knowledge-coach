"""Describe pawn and knight fork target roles and relative geometry."""

import chess

from .related_capture_position import _material, _phase


def features(board, move, piece, squares):
    direction = 1 if board.turn == chess.WHITE else -1
    geometry = tuple(
        sorted(
            (
                board.piece_type_at(square),
                chess.square_file(square) - chess.square_file(move.to_square),
                direction * (chess.square_rank(square) - chess.square_rank(move.to_square)),
            )
            for square in squares
        )
    )
    return {
        "mover": piece.piece_type,
        "target": tuple(sorted(board.piece_type_at(square) for square in squares)),
        "geometry": geometry,
        "material": _material(board),
        "phase": _phase(board),
    }
