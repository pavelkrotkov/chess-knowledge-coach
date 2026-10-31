"""Validate a complete imported puzzle line before practice begins."""

from __future__ import annotations

import chess

CORPUS_PLIES_LIMIT = 65


def validate_line(fen: str, solution: str) -> str:
    """Validate the complete line and return the position after the setup move."""
    try:
        board = chess.Board(fen)
        if not board.is_valid():
            raise ValueError("invalid board")
        moves = solution_moves(solution)
        for index, text in enumerate(moves):
            board.push(legal_move(board, text))
            if index == 0:
                prompt_fen = board.fen()
        return prompt_fen
    except (ValueError, TypeError):
        raise ValueError("invalid puzzle position or solution") from None


def legal_move(board: chess.Board, text: str) -> chess.Move:
    move = board.parse_uci(text)
    if not move or not board.is_legal(move):
        raise ValueError("illegal move")
    return move


def solution_moves(solution: str) -> list[str]:
    moves = solution.split()
    if len(moves) < 2 or len(moves) % 2:
        raise ValueError("invalid puzzle position or solution")
    return moves
