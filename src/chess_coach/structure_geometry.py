"""Pawn coordinates and isolated or hanging pawn patterns."""

from __future__ import annotations

import chess


def _pawns(board: chess.Board, color: chess.Color) -> list[chess.Square]:
    return list(board.pieces(chess.PAWN, color))


def _file(square: chess.Square) -> int:
    return chess.square_file(square)


def _rank(square: chess.Square) -> int:
    return chess.square_rank(square)


def _square_name(square: chess.Square) -> str:
    return chess.square_name(square)


def _pawn_files(board: chess.Board, color: chess.Color) -> set[int]:
    return {_file(square) for square in _pawns(board, color)}


def _isolated(board: chess.Board, color: chess.Color) -> list[str]:
    files = _pawn_files(board, color)
    return sorted(
        _square_name(square)
        for square in _pawns(board, color)
        if _file(square) - 1 not in files and _file(square) + 1 not in files
    )


def _hanging(board: chess.Board, color: chess.Color) -> list[str]:
    pawns = _pawns(board, color)
    result = []
    for square in pawns:
        for other in pawns:
            if _file(other) == _file(square) + 1 and _rank(other) == _rank(square):
                adjacent_files = {_file(square) - 1, _file(other) + 1}
                supported = any(_file(pawn) in adjacent_files for pawn in pawns)
                if not supported:
                    result.extend([_square_name(square), _square_name(other)])
    return sorted(set(result))
