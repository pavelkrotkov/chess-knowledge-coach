"""Detect backward pawns."""

from __future__ import annotations

import chess

from .structure_geometry import _file, _pawns, _rank, _square_name


def _backward(board: chess.Board, color: chess.Color) -> list[str]:
    pawns = _pawns(board, color)
    result = []
    direction = 1 if color == chess.WHITE else -1
    for square in pawns:
        file_index = _file(square)
        rank_index = _rank(square)
        neighbors = _advanced_neighbors(pawns, file_index, rank_index, direction)
        forward = _forward_square(file_index, rank_index, direction)
        if neighbors and forward is not None and board.attackers(not color, forward):
            result.append(_square_name(square))
    return sorted(result)


def _forward_square(file_index: int, rank_index: int, direction: int) -> chess.Square | None:
    rank = rank_index + direction
    return chess.square(file_index, rank) if 0 <= rank < 8 else None


def _advanced_neighbors(
    pawns: list[chess.Square], file_index: int, rank_index: int, direction: int
) -> list[chess.Square]:
    return [
        other
        for other in pawns
        if abs(_file(other) - file_index) == 1 and (_rank(other) - rank_index) * direction > 0
    ]
