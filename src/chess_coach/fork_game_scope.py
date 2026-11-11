"""Choose supported independent knight roots."""

import chess

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
