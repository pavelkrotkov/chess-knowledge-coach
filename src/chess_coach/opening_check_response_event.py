"""Describe complete legal check responses and the recorded choice."""

from .fact_fingerprint import canonical, digest
from .style_check_evasions import evasions


def _kind(move):
    if move["king_move"]:
        return "king"
    return "capture" if move["capture"] else "interposition"


def event(board, rows, ply, recorded):
    legal = evasions(board)
    if legal["status"] != "complete":
        raise ValueError("legal responses unavailable")
    options = {"king": 0, "capture": 0, "interposition": 0}
    played = None
    for move in legal["moves"]:
        kind = _kind(move)
        options[kind] += 1
        if recorded is not None and move["uci"] == recorded[2]:
            played = {"san": move["san"], "uci": move["uci"], "kind": kind}
    if recorded is not None and played is None:
        raise ValueError("recorded response unavailable")
    return {
        "ply": ply,
        "fen": board.fen(),
        "history_sha256": digest(canonical(rows)),
        "legal_responses": legal["count"],
        "response_classes": options,
        "played": played,
        "checkmate": board.is_checkmate(),
    }
