"""Show the finder for a current existing-pin capture source."""

import chess

from .objective_pin_prevent_existing import _matches
from .pin_existing import existing


def available(evidence):
    try:
        if evidence["pin_source_currentness"] != "current" or evidence["operation"] != "prevent":
            return False
        if evidence["review_status"] not in {"accepted", "unreviewed"}:
            return False
        return _capture(evidence)
    except (ValueError, TypeError, KeyError, IndexError):
        return False


def _capture(evidence):
    note = evidence["pin_explanation"]
    proof = note["proof"]
    if note["outcome"] not in {"success", "failure"} or proof["mode"] not in {
        "exposure",
        "pinned_capture",
    }:
        return False
    board = chess.Board(note["fen"])
    pins = existing(board)
    named = {
        "attacker": proof["pinner"],
        "pinned": proof["pinned"],
        "rear": proof["rear"],
        "kind": proof["type"],
    }
    if len(pins) != 1 or not _matches(pins[0], named):
        return False
    good = (
        evidence["context"]["played_move"]
        if note["outcome"] == "success"
        else note["alternative"]["move"]
    )
    move = board.parse_uci(good)
    return board.is_capture(move) and chess.square_name(move.to_square) == proof["pinner"]
