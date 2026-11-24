"""Reconstruct full public histories before inspecting a later window."""

import time

import chess

from .opening_full_history_input import load, verified_move
from .opening_public_fork_windows import bounds
from .opening_storage import position_key
from .style_history_lines import history_safe


def positions(db, row, binding, branch, deadline, *, window="continuation"):
    game_id, total, _ = row
    identity, moves = load(db, game_id, total)
    first, last = bounds(binding["ply"], total, window)
    decision = {"ply": binding["ply"], "catalog": {"parent": binding["source"]["parent"]}}
    board, rows, candidates = chess.Board(), [], []
    for ply, uci in enumerate(moves[:last], 1):
        if time.monotonic() >= deadline:
            raise TimeoutError("public fork deadline")
        if not history_safe(board):
            raise ValueError("draw-sensitive history")
        move = verified_move(board, uci, ply, decision, branch)
        if move.promotion:
            raise ValueError("promotion history unsupported")
        rows.append((ply, position_key(board), uci, board.san(move)))
        if ply >= first and ("white" if board.turn else "black") == binding["color"]:
            candidates.append((ply, board.copy(stack=True), move))
        board.push(move)
    return identity, moves, rows, candidates, total > last, history_safe(board)
