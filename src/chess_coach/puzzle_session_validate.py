"""Validate a complete imported puzzle line before practice begins."""

from __future__ import annotations

import chess


def validate_line(fen: str, solution: str) -> str:
    """Validate the complete line and return the position after the setup move."""
    try:
        board = chess.Board(fen)
        if not board.is_valid():
            raise ValueError("invalid board")
        moves = solution.split()
        if len(moves) < 2:
            raise ValueError("missing learner move")
        for index, text in enumerate(moves):
            board.push(legal_move(board, text))
            if index == 0:
                prompt_fen = board.fen()
        return prompt_fen
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid puzzle position or solution") from exc


def legal_move(board: chess.Board, text: str) -> chess.Move:
    move = board.parse_uci(text)
    if not move or not board.is_legal(move):
        raise ValueError("illegal move")
    return move
