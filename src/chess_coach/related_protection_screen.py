"""Cheap necessary conditions before the protection proof."""

import chess

from .pawn_scope import history_known
from .puzzle_session_validate import legal_move


def plausible(prompt, line, source):
    """Reject only roles and moves that cannot pass the full defense proof."""
    try:
        board = chess.Board(prompt)
        if not board.is_valid() or not history_known(board) or not line:
            return False
        move = legal_move(board, line[0])
        if board.piece_type_at(move.from_square) != source["mover"] or not _ordinary(board, move):
            return False
        return _roles(board, move, source)
    except (ValueError, TypeError, IndexError, KeyError, AttributeError):
        return False


def _ordinary(board, move):
    return not (
        board.is_check()
        or board.ep_square is not None
        or move.promotion
        or board.gives_check(move)
        or board.is_en_passant(move)
    )


def _roles(board, move, source):
    action = source["mechanism"]
    if action != "move_threatened_piece" and board.is_capture(move) != (
        action == "capture_attacker"
    ):
        return False
    return any(
        (square == move.from_square) == (action == "move_threatened_piece")
        and board.is_attacked_by(not board.turn, square)
        for square in board.pieces(source["target"], board.turn)
    )
