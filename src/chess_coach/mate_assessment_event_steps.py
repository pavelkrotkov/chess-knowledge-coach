"""Validate each actual assessment response and assistance event."""

import json

from .unified_session_moves import apply_move


def _hint(event, response, state):
    kind = event["submitted_move"]
    expected = {None: "hint", "reveal": "revealed"}.get(kind)
    if expected is None or response.get("feedback") != expected:
        raise ValueError("assessment assistance unavailable")
    state["hints"] += 1
    state["reveals"] += kind == "reveal"


def _move(event, response, row, state, lines):
    result = apply_move(row, lines, state["candidates"], event["submitted_move"])
    if any(
        result.get(key) != response.get(key)
        for key in ("feedback", "status", "fen", "opponent_move")
    ):
        raise ValueError("assessment move history unavailable")
    row.update(current_fen=result["fen"], status=result["status"], next_index=result["next_index"])
    state["candidates"] = result["candidates"]
    state["feedback"] = result["feedback"]
    state["illegal"] += result["feedback"] == "illegal"


def check_event(event, row, state, lines):
    if row["status"] != "active":
        raise ValueError("events follow completed assessment")
    response = json.loads(event["response_json"])
    if event["kind"] == "hint":
        _hint(event, response, state)
    elif event["kind"] == "move":
        _move(event, response, row, state, lines)
    else:
        raise ValueError("unsupported assessment event")
    if (response.get("hints_used"), response.get("fen"), response.get("status")) != (
        state["hints"],
        row["current_fen"],
        row["status"],
    ):
        raise ValueError("assessment event state mismatch")
