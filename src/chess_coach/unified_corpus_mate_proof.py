"""Prove that a reset corpus prompt supplies immediate checkmate."""

import chess

from .puzzle_session_validate import CORPUS_PLIES_LIMIT, legal_move, solution_moves, validate_line


def certify(row):
    moves = solution_moves(row["solution"])
    if len(moves) > CORPUS_PLIES_LIMIT:
        raise ValueError("practice line exceeds the supported bound")
    prompt = validate_line(row["fen"], row["solution"])
    board = chess.Board(row["fen"])
    setup = legal_move(board, moves[0])
    if not board.is_zeroing(setup):
        raise ValueError("practice history is unavailable")
    board.push(setup)
    if board.fen() != prompt or board.is_game_over(claim_draw=True):
        raise ValueError("practice prompt is unavailable")
    board.push(legal_move(board, moves[1]))
    if not board.is_checkmate():
        raise ValueError("supplied move is not immediate mate")
    return prompt


def eligible(row):
    try:
        certify(row)
        return True
    except (ValueError, TypeError, KeyError):
        return False
