"""Validate one full public opening and detect available center choices."""

import time

import chess

from .opening_fit_replay_step import selected, step
from .style_early_center import MAX_PLY


def inspect(rows, color, deadline, *, decision=None):
    if len(rows) != MAX_PLY:
        return "inconsistent", False
    board = chess.Board()
    found = False
    try:
        for ply, row in enumerate(rows, 1):
            if time.monotonic() >= deadline:
                raise TimeoutError("opening fit deadline")
            selected(board, row, ply, decision)
            found |= step(board, row, ply, color, decision["ply"] if decision else 0)
    except (ValueError, TypeError):
        return "inconsistent", False
    return "valid", found
