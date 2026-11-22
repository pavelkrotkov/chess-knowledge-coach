"""Replay an admitted public game through its final bounded later window."""

import time

import chess

from .fact_fingerprint import canonical, digest
from .opening_full_history_input import load, verified_move
from .opening_full_history_position import example as position_example
from .opening_profile_play import STORED_PLIES
from .opening_reference_play import MAX_GAME_PLIES

WINDOW = 36
POLICY = {
    "games_per_branch": 10,
    "after_ply": STORED_PLIES,
    "tail_positions": WINDOW,
    "maximum_game_plies": MAX_GAME_PLIES,
}


def replay(db, row, decision, branch, deadline):
    game_id, total, context = row
    identity, moves = load(db, game_id, total)
    board = chess.Board()
    first = max(STORED_PLIES + 1, total - WINDOW + 1)
    example = None
    for ply, uci in enumerate(moves, 1):
        if time.monotonic() >= deadline:
            raise TimeoutError("public history deadline")
        move = verified_move(board, uci, ply, decision, branch)
        if ply == first:
            example = position_example(board, moves, ply, move, first, total)
        board.push(move)
    outcome = board.outcome(claim_draw=False)
    return {
        "record": game_id,
        "identity": identity,
        "history_sha256": digest(canonical(moves)),
        "context_sha256": digest(context),
        "total_plies": total,
        "record_ended": True,
        "board_terminal": outcome is not None,
        "terminal_reason": outcome.termination.name if outcome else None,
        "censored": first > STORED_PLIES + 1,
        "example": example,
    }
