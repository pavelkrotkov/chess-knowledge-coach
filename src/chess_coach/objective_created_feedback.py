"""Display only a legal witness from a completed named-piece verification."""

import json

import chess

from .related_created_objective import is_source


def annotate(view, session, result_row):
    if not is_source(session) or view.get("status") != "incorrect":
        return
    try:
        result = json.loads(result_row["result_json"])
        board = chess.Board(session["current_fen"])
        reply = board.parse_uci(result["capture_reply"])
        if board.is_capture(reply):
            view["capture_san"] = board.san(reply)
    except (ValueError, TypeError, KeyError):
        return
