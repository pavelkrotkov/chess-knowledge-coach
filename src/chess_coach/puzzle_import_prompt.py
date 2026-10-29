"""Validate puzzle solutions and derive learner-facing position features."""

import chess

from .puzzle_session_validate import validate_line


def attach_prompt(result: dict) -> None:
    try:
        prompt = validate_line(result["fen"], result["solution"])
        board = chess.Board(prompt)
        result.update(
            prompt_fen=prompt,
            prompt_key=" ".join(prompt.split()[:4]),
            prompt_turn="white" if board.turn else "black",
            prompt_material=_material(board),
            valid=True,
        )
    except ValueError:
        result["valid"] = False


def _material(board: chess.Board) -> str:
    return ",".join(
        str(len(board.pieces(piece, color)))
        for color in (chess.WHITE, chess.BLACK)
        for piece in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
    )
