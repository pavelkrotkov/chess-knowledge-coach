"""Validate each ordered public move and its selected opening branch."""

from .opening_storage import position_key
from .style_early_center import eligible
from .style_history_lines import history_safe


def step(board, row, ply, color, after):
    number, parent, uci, san = row
    if number != ply or position_key(board) != parent or not history_safe(board):
        raise ValueError("public opening history unavailable")
    move = board.parse_uci(uci)
    if move.promotion or board.san(move) != san:
        raise ValueError("public opening move unavailable")
    found = ply > after and board.turn == (color == "white") and eligible(board, ply)
    board.push(move)
    return found


def selected(board, row, ply, decision):
    if decision is None or ply != decision["ply"]:
        return
    if position_key(board) != decision["parent"] or row[2] != decision["move"]:
        raise ValueError("public opening branch differs")
