"""Inspect a single same-board engine comparison with game history."""

import json

from .db import Database
from .decision_history import decision_board
from .decision_line_view import view_line


def inspect_decision(db: Database, position_id: int, *, run_id: int | None = None) -> dict:
    position = db.connection.execute(
        """SELECT p.*, g.pgn, g.variant FROM positions p JOIN games g ON g.id=p.game_id
        WHERE p.id=?""",
        (position_id,),
    ).fetchone()
    if position is None:
        raise ValueError("unknown decision")
    board = decision_board(db, position)
    run = _run(db, position["game_id"], run_id)
    run_view = dict(run) if run else None
    if run_view is not None:
        run_view["config"] = json.loads(run_view.pop("config_json"))
    result = {
        "position_id": position_id,
        "game_id": position["game_id"],
        "ply": position["ply"],
        "decision_fen": board.fen(),
        "score_pov": "white" if board.turn else "black",
        "played_move": position["uci"],
        "played_san": board.san(board.parse_uci(position["uci"])),
        "run": run_view,
        "best": None,
        "played": None,
        "status": "analysis_unavailable",
        "note": "Each line is a separate bounded search, not a skill or mastery assessment.",
    }
    if run is not None:
        _add_lines(db, result, board, run["id"])
    return result


def _run(db, game_id, run_id):
    if run_id is not None:
        row = db.connection.execute(
            "SELECT * FROM analysis_runs WHERE id=? AND game_id=?", (run_id, game_id)
        ).fetchone()
        if row is None:
            raise ValueError("unknown analysis run for decision")
        return row
    return db.connection.execute(
        "SELECT * FROM analysis_runs WHERE game_id=? ORDER BY id DESC LIMIT 1", (game_id,)
    ).fetchone()


def _add_lines(db, result, board, run_id):
    rows = db.connection.execute(
        "SELECT * FROM decision_analysis_lines WHERE run_id=? AND position_id=? ORDER BY role",
        (run_id, result["position_id"]),
    ).fetchall()
    for row in rows:
        result[row["role"]] = view_line(row, board, result["played_move"])
    if result["best"] and result["played"]:
        result["status"] = (
            "limited"
            if all(result[key]["status"] == "limited" for key in ("best", "played"))
            else "incomplete"
        )
