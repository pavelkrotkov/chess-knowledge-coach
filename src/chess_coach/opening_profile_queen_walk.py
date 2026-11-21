"""Recheck ordered history and count queen states after one exact decision."""

import time

import chess

from .opening_profile_queen_move import state, step
from .opening_storage import position_key


def walk(rows, decision, move, status, deadline):
    first = decision["ply"]
    result = {
        "status": status,
        "start": None,
        "queenless_observed": False,
        "one_or_imbalanced": False,
    }
    board = chess.Board()
    for ply, row in enumerate(rows, 1):
        if time.monotonic() >= deadline:
            raise TimeoutError("opening profile deadline")
        if ply == first:
            if position_key(board) != decision["catalog"]["parent"] or row[2] != move:
                raise ValueError("branch unavailable")
            result["start"] = state(board)
            result["one_or_imbalanced"] = result["start"] == "start_imbalanced"
        if not step(board, row, ply):
            result["status"] = "unsupported"
            break
        if ply >= first:
            _observe(result, board)
    return result


def _observe(result, board):
    observed = state(board)
    result["one_or_imbalanced"] |= observed == "start_imbalanced"
    result["queenless_observed"] |= (
        result["start"] != "preexisting_queenless" and observed == "preexisting_queenless"
    )
