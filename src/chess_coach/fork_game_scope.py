"""Choose supported independent knight roots."""

import chess

from .fork_targets import targets
from .pawn_scope import history_known


def supported(board):
    return (
        board.is_valid()
        and history_known(board)
        and not board.is_game_over(claim_draw=True)
        and not board.is_check()
        and board.ep_square is None
        and not board.is_repetition(2)
        and not board.is_fifty_moves()
    )


def roots(board):
    return sorted(
        (
            move
            for move in board.legal_moves
            if board.piece_type_at(move.from_square) == chess.KNIGHT and not board.is_capture(move)
        ),
        key=lambda move: move.uci(),
    )


def bind_root(board, row):
    move, stored, state = row
    parsed = board.parse_uci(move)
    if parsed not in roots(board) or state not in {"proved", "unknown", "outside"}:
        raise ValueError("fork root source changed")
    shape = targets(board, parsed)
    if state == "proved":
        if shape is None:
            raise ValueError("fork targets changed")
        squares = list(shape[1])
        expected = [chess.square_name(square) for square in squares]
    else:
        squares = list(shape[1]) if shape else []
        expected = []
    if stored != expected:
        raise ValueError("fork root state changed")
    return parsed, squares
