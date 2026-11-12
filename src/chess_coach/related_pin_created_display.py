"""Expose only a current supported owned pin contrast."""

import chess

from .objective_pin_prevent_origin import _created


def available(evidence):
    try:
        if evidence["pin_source_currentness"] != "current" or evidence["operation"] != "prevent":
            return False
        if evidence["review_status"] not in {"accepted", "unreviewed"}:
            return False
        return _supported(evidence)
    except (ValueError, TypeError, KeyError, IndexError):
        return False


def _supported(evidence):
    note = evidence["pin_explanation"]
    proof = note["proof"]
    if note["outcome"] not in {"success", "failure"} or proof.get("mode") in {
        "exposure",
        "pinned_capture",
    }:
        return False
    board = chess.Board(note["fen"])
    played = board.parse_uci(evidence["context"]["played_move"])
    other = board.parse_uci(note["alternative"]["move"])
    if played == other or played not in board.legal_moves or other not in board.legal_moves:
        return False
    bad, good = (played, other) if note["outcome"] == "failure" else (other, played)
    return bool(_created(board, proof, bad, good))
