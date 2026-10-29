"""Rebuild played positions without looking ahead in the solution."""

import json

import chess


def _steps(prompt, current, rows):
    board = chess.Board(prompt)
    steps = [{"fen": board.fen(), "label": "Starting position"}]
    for row in rows:
        response = json.loads(row["response_json"])
        if response["feedback"] == "illegal":
            continue
        if response.get("opponent_before_move"):
            _append(board, response["opponent_before_move"], "Reply", steps)
        _append(board, row["submitted_move"], "You", steps)
        if response.get("opponent_move"):
            _append(board, response["opponent_move"], "Reply", steps)
        if board.fen() != chess.Board(response["fen"]).fen():
            raise ValueError("history mismatch")
    if board.fen() != chess.Board(current).fen():
        raise ValueError("history mismatch")
    return steps


def _append(board, text, actor, steps):
    move = board.parse_uci(text)
    san = board.san(move)
    board.push(move)
    steps.append({"fen": board.fen(), "label": actor + ": " + san})
