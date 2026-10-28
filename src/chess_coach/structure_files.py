"""Detect open and half-open files."""

from __future__ import annotations

import chess

from .structure_geometry import _file, _pawn_files

_FILES = "abcdefgh"


def _open_files(board: chess.Board) -> list[str]:
    return [
        _FILES[file_index]
        for file_index in range(8)
        if not any(_file(square) == file_index for square in board.pieces(chess.PAWN, chess.WHITE))
        and not any(_file(square) == file_index for square in board.pieces(chess.PAWN, chess.BLACK))
    ]


def _half_open_files(board: chess.Board, color: chess.Color) -> list[str]:
    own = _pawn_files(board, color)
    enemy = _pawn_files(board, not color)
    return [_FILES[index] for index in range(8) if index not in own and index in enemy]
