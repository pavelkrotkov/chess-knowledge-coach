"""Replay a prepared short-mate line and the actual final checkmate."""

import json

import chess

from .objective_events import response
from .objective_history_replay import replay
from .puzzle_session_validate import legal_move


def completed(row, events):
    board = chess.Board(row["prompt_fen"])
    root = None
    for index, event in enumerate(events):
        detail = response(event)
        if event["kind"] != "move":
            return False
        if detail.get("feedback") == "objective_verified":
            if root is None or index != len(events) - 1:
                return False
            return _final(row, board, event, detail, root)
        if detail.get("feedback") == "line_match":
            if root is not None:
                return False
            root = [event["submitted_move"], detail.get("opponent_move")]
        replay(board, event)
    return False


def _final(row, board, event, detail, root):
    move = legal_move(board, event["submitted_move"])
    if [*root, move.uci()] not in json.loads(row["lines_json"]):
        return False
    board.push(move)
    return board.is_checkmate() and detail.get("fen") == row["current_fen"] == board.fen()
