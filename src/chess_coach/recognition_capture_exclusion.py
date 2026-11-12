"""Exclude mate prompts with any unresolved competing capture."""

import time

from .objective_capture_judge import judge

SECONDS = 1.5


def no_capture(board):
    started = time.monotonic()
    for move in board.legal_moves:
        if not board.is_capture(move):
            continue
        result = judge(
            board,
            move,
            "bounded_material_gain",
            move.to_square,
            3,
            time.monotonic,
            started,
            SECONDS,
            {},
        )
        if result["status"] != "incorrect":
            return False
    return time.monotonic() - started <= SECONDS
