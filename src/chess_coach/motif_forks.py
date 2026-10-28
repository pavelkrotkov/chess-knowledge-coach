"""Detect attacks on multiple valuable pieces."""

from typing import Any

import chess

_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}


def _legal_targets(board: chess.Board, attacker: chess.Square) -> list[chess.Square]:
    return [
        move.to_square
        for move in board.legal_moves
        if move.from_square == attacker and board.piece_at(move.to_square) is not None
    ]


def _valuable_enemy_target(board: chess.Board, square: chess.Square, color: chess.Color) -> bool:
    target = board.piece_at(square)
    return target is not None and target.color != color and _VALUES[target.piece_type] >= 3


def _forks(board: chess.Board) -> list[dict[str, Any]]:
    facts = []
    for attacker in chess.SQUARES:
        piece = board.piece_at(attacker)
        if piece is None or piece.color != board.turn:
            continue
        targets = [
            square
            for square in _legal_targets(board, attacker)
            if _valuable_enemy_target(board, square, piece.color)
        ]
        if len(targets) >= 2:
            facts.append(
                {
                    "motif": "fork",
                    "attacker": chess.square_name(attacker),
                    "targets": sorted(chess.square_name(square) for square in targets),
                }
            )
    return facts
