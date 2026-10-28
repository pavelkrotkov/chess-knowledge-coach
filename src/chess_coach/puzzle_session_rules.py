"""Validate a puzzle line and apply one learner action."""

from __future__ import annotations

import chess

from .puzzle_session_validate import legal_move


def apply_move(fen: str, solution: str, index: int, submitted: str) -> dict[str, object]:
    board = chess.Board(fen)
    try:
        move = legal_move(board, submitted)
    except ValueError:
        return {"feedback": "illegal", "fen": fen, "next_index": index, "status": "active"}
    expected = solution.split()
    board.push(move)
    if move.uci() != expected[index] and not board.is_checkmate():
        return {
            "feedback": "incorrect",
            "fen": board.fen(),
            "next_index": index,
            "status": "failed",
        }
    next_index = index + 1
    opponent_move = None
    if not board.is_checkmate() and next_index < len(expected):
        opponent_move = expected[next_index]
        board.push(legal_move(board, opponent_move))
        next_index += 1
    status = "solved" if board.is_checkmate() or next_index == len(expected) else "active"
    return {
        "feedback": "correct",
        "fen": board.fen(),
        "next_index": next_index,
        "status": status,
        "opponent_move": opponent_move,
    }


def hint_square(solution: str, index: int) -> str:
    return chess.square_name(chess.Move.from_uci(solution.split()[index]).from_square)
