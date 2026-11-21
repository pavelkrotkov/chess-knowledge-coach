"""Display a legal named rear-capture witness after a failed slide."""

import json

import chess

from .objective_pin_slide_contract import is_source


def annotate(view, session, result_row):
    if not is_source(session) or view.get("status") != "incorrect":
        return
    try:
        proof = json.loads(result_row["result_json"])["proof"]
        board = chess.Board(session["current_fen"])
        move = board.parse_uci(proof["move"])
        if board.is_capture(move) and chess.square_name(move.to_square) == proof["rear"]:
            view["capture_san"] = board.san(move)
    except (ValueError, TypeError, KeyError):
        return
