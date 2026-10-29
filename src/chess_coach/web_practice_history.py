"""Reconstruct only played moves for bounded, read-only board navigation."""

import json

import chess

from .puzzle_session_state import _session
from .puzzle_session_validate import validate_line
from .unified_session_state import session_row
from .web_practice_history_steps import _steps

LIMIT = 512


def unified_history(db, attempt, subject):
    row = session_row(db, attempt, subject)
    return _history(db, "unified_session_events", attempt, row["prompt_fen"], row["current_fen"])


def puzzle_history(db, attempt):
    row = _session(db, attempt)
    prompt = validate_line(row["initial_fen"], row["solution"])
    steps = _history(db, "puzzle_session_events", attempt, prompt, row["current_fen"])
    color = "white" if chess.Board(prompt).turn else "black"
    return steps, color


def _history(db, table, attempt, prompt, current):
    rows = db.connection.execute(
        f"SELECT submitted_move,response_json FROM {table} WHERE attempt_id=? AND kind='move' ORDER BY rowid LIMIT ?",
        (attempt, LIMIT + 1),
    ).fetchall()
    if len(rows) > LIMIT:
        return [{"fen": current, "label": "Current position"}]
    try:
        return _steps(prompt, current, rows)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return [{"fen": current, "label": "Current position"}]


def selected_step(steps, raw):
    if raw is None:
        return len(steps) - 1
    if not raw.isascii() or not raw.isdecimal() or len(raw) > 4:
        raise ValueError("invalid history position")
    index = int(raw)
    if index >= len(steps):
        raise ValueError("invalid history position")
    return index
