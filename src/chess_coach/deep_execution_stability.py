"""Compare bounded search estimates only under matching recorded provenance."""

import json

from .decision_line_view import view_line
from .deep_execution_compare import compare_scores
from .deep_execution_identity import comparable_engine


def stability(db, selection, position, board, result, config):
    row = db.connection.execute(
        "SELECT config_json FROM analysis_runs WHERE id=? AND game_id=?",
        (selection["cheap_run_id"], selection["game_id"]),
    ).fetchone()
    if row is None:
        return "incomparable", False
    try:
        cheap_config = json.loads(row["config_json"])
    except (TypeError, ValueError):
        return "incomparable", False
    if not isinstance(cheap_config, dict) or not comparable_engine(cheap_config, config):
        return "incomparable", False
    rows = db.connection.execute(
        "SELECT * FROM decision_analysis_lines WHERE run_id=? AND position_id=?",
        (selection["cheap_run_id"], position["id"]),
    ).fetchall()
    cheap = {row["role"]: view_line(row, board, position["uci"]) for row in rows}
    comparable, unstable = compare_scores(cheap, result, board, position["uci"])
    return ("comparable" if comparable else "incomparable"), unstable
