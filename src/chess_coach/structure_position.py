"""Detect file, space, and pawn-distribution features."""

from __future__ import annotations

import chess

from .structure_geometry import _file, _pawns, _rank


def _minority(board: chess.Board, color: chess.Color) -> list[str]:
    enemy = not color
    result = []
    for name, files in (("queenside", range(4)), ("kingside", range(4, 8))):
        own_count = sum(_file(square) in files for square in _pawns(board, color))
        enemy_count = sum(_file(square) in files for square in _pawns(board, enemy))
        if own_count < enemy_count:
            result.append(name)
    return result


def _space(board: chess.Board, color: chess.Color) -> int:
    target_ranks = range(4, 8) if color == chess.WHITE else range(0, 4)
    return sum(
        1
        for pawn in _pawns(board, color)
        for target in board.attacks(pawn)
        if _rank(target) in target_ranks
    )


def _locked_center(board: chess.Board) -> bool:
    center = (chess.D4, chess.E4, chess.D5, chess.E5)
    return all(
        board.piece_at(square) == chess.Piece(chess.PAWN, color)
        for square, color in (
            (chess.D4, chess.WHITE),
            (chess.E4, chess.WHITE),
            (chess.D5, chess.BLACK),
            (chess.E5, chess.BLACK),
        )
    ) and all(board.piece_at(square) is not None for square in center)
