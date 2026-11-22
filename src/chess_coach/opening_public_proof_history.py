"""Reconstruct the original public game prefix before examining a branch."""

import time

import chess

from .opening_profile_queen_move import step
from .opening_profile_queen_replay import _end
from .opening_storage import position_key
from .style_history_lines import history_safe


def _step(board, entry, ply, binding, branch, deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError("public proof deadline")
    if ply == binding["ply"] and (
        position_key(board) != binding["source"]["parent"] or entry[2] != branch
    ):
        raise ValueError("public branch differs")
    previous = board.copy(stack=True)
    if not step(board, entry, ply):
        raise ValueError("public history unsupported")
    return previous


def _candidate(board, entry, ply, binding, all_moves):
    if ply < binding["ply"] or ("white" if board.turn else "black") != binding["color"]:
        return None
    move = board.parse_uci(entry[2])
    return move if all_moves or board.is_capture(move) else None


# Structural transposition keys omit history; keep the original move stack for proof.
def positions(db, game_id, total, binding, branch, deadline, *, all_moves=False):
    first = binding["ply"]
    last, frontier = _end(first, total)
    rows = db.execute(
        "SELECT ply,parent,uci,san FROM moves WHERE game_id=? AND ply<=? ORDER BY ply",
        (game_id, last),
    ).fetchall()
    if first < 1 or last < first or len(rows) != last:
        raise ValueError("public history incomplete")
    board, captures = chess.Board(), []
    for ply, entry in enumerate(rows, 1):
        previous = _step(board, entry, ply, binding, branch, deadline)
        move = _candidate(previous, entry, ply, binding, all_moves)
        if move is not None:
            captures.append((ply, previous, move))
    return rows, captures, frontier != "ended", history_safe(board)
