"""Reveal one supplied continuation only after recording a hint."""

import json

import chess

from .puzzle_session_events import request_hint as puzzle_hint
from .puzzle_session_state import _session
from .puzzle_session_validate import solution_moves, validate_line
from .unified_session_events import hint as unified_hint
from .unified_session_state import session_row
from .unified_source_current import require_current
from .web_board import board_rows


def unified_reveal(db, attempt, subject, event):
    unified_hint(db, attempt, subject, event_id=event)
    row = session_row(db, attempt, subject)
    require_current(db, row)
    lines = json.loads(row["lines_json"])
    candidates = json.loads(row["candidates_json"])
    return _positions(
        row["current_fen"], lines[candidates[0]][row["next_index"] :], row["learner_color"]
    )


def puzzle_reveal(db, attempt, event):
    puzzle_hint(db, attempt, event_id=event)
    row = _session(db, attempt)
    prompt = validate_line(row["initial_fen"], row["solution"])
    color = "white" if chess.Board(prompt).turn else "black"
    return _positions(
        row["current_fen"], solution_moves(row["solution"])[row["next_index"] :], color
    )


def _positions(fen, moves, color):
    if not moves or len(moves) > 65:
        raise ValueError("continuation unavailable")
    board = chess.Board(fen)
    result = []
    for text in moves:
        move = board.parse_uci(text)
        san = board.san(move)
        board.push(move)
        result.append({"san": san, "board": board_rows(board.fen(), color), "color": color})
    return result
