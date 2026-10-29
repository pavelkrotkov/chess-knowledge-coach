"""Reveal one supplied continuation only after recording a hint."""

import chess

from .puzzle_session_events import request_hint as puzzle_hint
from .puzzle_session_state import _session
from .puzzle_session_validate import solution_moves, validate_line
from .unified_session_events import reveal as unified_reveal_event
from .unified_session_state import session_row
from .unified_source_current import require_current
from .web_board import board_rows
from .web_move_history import unified_input_fen


def unified_reveal(db, attempt, subject, event):
    result = unified_reveal_event(db, attempt, subject, event_id=event)
    row = session_row(db, attempt, subject)
    require_current(db, row)
    fen = unified_input_fen(db, attempt, subject, event, row["current_fen"])
    return _positions(fen, result["revealed_line"].split(), row["learner_color"])


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
