"""Validate one full public opening and detect available center choices."""

import time

import chess

from .opening_storage import position_key
from .style_early_center import MAX_PLY, eligible
from .style_history_lines import history_safe


def _step(board, row, ply, color):
    number, parent, uci, san = row
    if number != ply or position_key(board) != parent or not history_safe(board):
        raise ValueError("public opening history unavailable")
    move = board.parse_uci(uci)
    if move.promotion or board.san(move) != san:
        raise ValueError("public opening move unavailable")
    found = board.turn == (color == "white") and eligible(board, ply)
    board.push(move)
    return found


def inspect(rows, color, deadline):
    if len(rows) != MAX_PLY:
        return "inconsistent", False
    board = chess.Board()
    found = False
    try:
        for ply, row in enumerate(rows, 1):
            if time.monotonic() >= deadline:
                raise TimeoutError("opening fit deadline")
            found |= _step(board, row, ply, color)
    except (ValueError, TypeError):
        return "inconsistent", False
    return "valid", found
