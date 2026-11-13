"""Nominate actual early central pawn choices without inspecting the played root."""

from .style_center_capture import capture

MAX_PLY = 20


def eligible(board, ply):
    if not 1 <= ply <= MAX_PLY or board.is_check():
        return False
    moves = list(board.legal_moves)
    if len(moves) < 2:
        return False
    options = {bool((item := capture(board, move, 1)) and item["central"]) for move in moves}
    return options == {False, True}
