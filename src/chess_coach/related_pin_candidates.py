"""Normalize external setup and inspect its bounded candidate lines."""

import chess

from .puzzle_session_validate import CORPUS_PLIES_LIMIT, legal_move, solution_moves
from .related_pin_line import candidate_line
from .related_pin_public import lines as public_lines


def prompt(item):
    board = chess.Board(item["fen"])
    if not board.is_valid() or board.is_game_over(claim_draw=True):
        raise ValueError("candidate position unavailable")
    if item["type"] == "corpus":
        moves = solution_moves(item["solution"])
        if len(moves) > CORPUS_PLIES_LIMIT:
            raise ValueError("practice line exceeds the supported bound")
        board.push(legal_move(board, moves[0]))
        return board, [" ".join(moves[1:])]
    if item.get("objective") not in {"legal_line", "checkmate"}:
        raise ValueError("unsupported public objective")
    return board, public_lines(item)


def matches(board, lines, source, budget):
    found = []
    for index, text in enumerate(lines):
        result = candidate_line(board, text.split(), source, budget)
        if result is not None:
            found.append((index, result))
        if budget["truncated"]:
            break
    return found
