"""Replay bounded immutable assessment events, including assistance."""

import json

from .mate_assessment_event_steps import check_event
from .mate_assessment_outcome import outcome
from .objective_events import MAX_EVENTS


def _event_rows(db, attempt):
    rows = db.connection.execute(
        """SELECT kind,submitted_move,response_json FROM unified_session_events
        WHERE attempt_id=? ORDER BY rowid LIMIT ?""",
        (attempt, MAX_EVENTS + 1),
    ).fetchall()
    if len(rows) > MAX_EVENTS:
        raise ValueError("assessment events truncated")
    return rows


def replay(db, original):
    lines = json.loads(original["lines_json"])
    row = dict(original)
    row.update(current_fen=row["prompt_fen"], status="active", next_index=0)
    state = {
        "candidates": list(range(len(lines))),
        "hints": 0,
        "reveals": 0,
        "illegal": 0,
        "feedback": None,
    }
    for event in _event_rows(db, row["attempt_id"]):
        check_event(event, row, state, lines)
    for key in ("current_fen", "status", "next_index"):
        if row[key] != original[key]:
            raise ValueError("assessment state mismatch")
    if state["candidates"] != json.loads(original["candidates_json"]):
        raise ValueError("assessment candidate mismatch")
    if state["hints"] != original["hints_used"]:
        raise ValueError("assessment assistance mismatch")
    return {key: state[key] for key in ("hints", "reveals", "illegal")} | {
        "outcome": outcome(row, state["feedback"])
    }
