"""Restrict proof to valid one-pawn-per-side roots with known history."""

import chess


def supported(board):
    if not _standard(board):
        return False
    if board.occupied.bit_count() > 4 or not board.pawns:
        return False
    if board.occupied != board.kings | board.pawns:
        return False
    return all(len(board.pieces(chess.PAWN, color)) <= 1 for color in chess.COLORS)


def _standard(board):
    return (
        type(board) is chess.Board
        and board.is_valid()
        and not board.castling_rights
        and not board.chess960
    )


def history_known(board):
    return board.root().halfmove_clock == 0 or board.halfmove_clock < len(board.move_stack)
