"""Match an independently replayed discovered checkmate."""

import chess

from .puzzle_session_validate import legal_move, solution_moves
from .related_capture_match import _scored
from .related_capture_position import prompt_key
from .related_discovery_source import shape
from .related_fork_lines import bind_lines


def prompt(fen, solution):
    moves = solution_moves(solution)
    if len(moves) != 2:
        raise ValueError("immediate mate required")
    board = chess.Board(fen)
    if not board.is_valid():
        raise ValueError("invalid puzzle position")
    setup = legal_move(board, moves[0])
    if not board.is_zeroing(setup):
        raise ValueError("setup history unavailable")
    board.push(setup)
    move = legal_move(board, moves[1])
    return board, move, moves[1]


def candidate(item, source, seen, baseline):
    if item["type"] != "corpus":
        return None
    try:
        board, move, line = prompt(item["fen"], item["solution"])
        features = shape(board, move)
        if not features or features["geometry"] != source["geometry"]:
            return None
        key = prompt_key(board.fen())
        if key in seen:
            return None
        scored = _scored(item, source, features, board.fen(), key, baseline)
        bind_lines(scored, [line], [0])
        return scored
    except (ValueError, TypeError, KeyError, IndexError):
        return None
