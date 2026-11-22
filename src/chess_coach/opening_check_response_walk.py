"""Walk verified public moves and inspect check responses for one side."""

import time

import chess

from .opening_check_response_event import event
from .opening_check_response_terminal import finish
from .opening_profile_queen_move import step
from .opening_storage import position_key


def _move(board, row, ply, decision, move):
    first = decision["ply"]
    if ply == first and (position_key(board) != decision["catalog"]["parent"] or row[2] != move):
        raise ValueError("branch unavailable")
    previous = board.copy(stack=True)
    if not step(board, row, ply):
        raise ValueError("unsupported history")
    return previous


def walk(rows, decision, move, deadline, result):
    first = decision["ply"]
    board = chess.Board()
    color = first % 2 == 1
    for ply, row in enumerate(rows, 1):
        if time.monotonic() >= deadline:
            raise TimeoutError("check response deadline")
        previous = _move(board, row, ply, decision, move)
        if ply >= first and previous.turn == color and previous.is_check():
            result["events"].append(event(previous, rows[: ply - 1], ply, row))
    finish(board, rows, first, color, result)
    return result
