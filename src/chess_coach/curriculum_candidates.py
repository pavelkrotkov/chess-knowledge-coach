"""Verify supported puzzle tasks and return safe prompt details."""

import chess

from .puzzle_session_validate import legal_move, solution_moves, validate_line


def verified_candidate(row) -> dict | None:
    try:
        if len(row["solution"].split(maxsplit=2)) != 2:
            return None
        prompt = validate_line(row["fen"], row["solution"])
        board = chess.Board(prompt)
        move = legal_move(board, solution_moves(row["solution"])[1])
        key = " ".join(board.fen().split()[:4])
        board.push(move)
        if not board.is_checkmate():
            return None
    except (ValueError, TypeError, IndexError):
        return None
    return {
        "corpus_version": row["version"],
        "puzzle_id": row["puzzle_id"],
        "rating": row["rating"],
        "prompt_fen": prompt,
        "prompt_key": key,
        "skill": "mate_in_one",
        "operation": "execute",
        "objective": "Find mate in one.",
    }
