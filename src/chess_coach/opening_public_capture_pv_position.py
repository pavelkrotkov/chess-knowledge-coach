"""Nominate and evaluate one public position under bounded capture rules."""

import time

from .material_ambiguity import ambiguous
from .material_capture import capture_observation
from .material_capture_gain import capture_gain
from .material_reply_guard import unresolved_reply
from .opening_public_capture_pv_session import analyze
from .opening_queue_reference import public

MAX_CAPTURES = 32


def check(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError("public capture deadline")


def candidate(board, recorded, deadline):
    moves = (
        [recorded]
        if board.is_capture(recorded)
        else [move for move in board.legal_moves if board.is_capture(move)]
    )
    if len(moves) > MAX_CAPTURES:
        return False

    def within():
        check(deadline)

    for move in moves:
        within()
        _, reason, _ = capture_gain(board, move, board.piece_at(move.to_square), check=within)
        if reason is None and not unresolved_reply(board, move, check=within):
            return True
    return False


def observe(board, recorded, engine, deadline):
    def within():
        check(deadline)

    within()
    config, result = analyze(board, recorded.uci(), engine, deadline)
    within()
    qualified = public(result, recorded.uci(), board)
    observed = ambiguous("material_capture", "native_reference_unavailable")
    if qualified:
        best = result["lines"][0]
        actual = next(line for line in result["lines"] if line["root_move"] == recorded.uci())
        selected = recorded if board.is_capture(recorded) else board.parse_uci(best["root_move"])
        observed = (
            capture_observation(board, selected, recorded, best, actual, check=within)
            if board.is_capture(selected)
            else ambiguous("material_capture", "native_best_not_capture")
        )
    within()
    return {
        "configuration": config,
        "native": result,
        "qualified": qualified,
        "observation": observed,
    }
