"""Present validated native deep lines with shared search-work accounting."""

import json

from .decision_line_view import view_line


def run_view(db, attempt, position_id, board, played):
    run_id = attempt["analysis_run_id"]
    if run_id is None:
        return None
    run = db.connection.execute("SELECT * FROM analysis_runs WHERE id=?", (run_id,)).fetchone()
    if run is None:
        return None
    config = _decode(run["config_json"])
    if not isinstance(config, dict):
        return None
    keys = ("nodes", "time_limit", "multipv", "played_multipv", "threads", "hash_mb", "min_depth")
    lines = db.connection.execute(
        "SELECT * FROM decision_analysis_lines WHERE run_id=? AND position_id=? ORDER BY role",
        (run_id, position_id),
    ).fetchall()
    result = {
        "run_id": run_id,
        "engine": run["engine"],
        "engine_version": run["engine_version"],
        "limits": {key: config.get(key) for key in keys},
        "best": None,
        "played": None,
        "alternatives": [],
        "best_work": _decode(attempt["best_work_json"]),
        "played_work": _decode(attempt["played_work_json"]),
    }
    for line in lines:
        result[line["role"]] = view_line(line, board, played)
    result["alternatives"] = _alternatives(db, attempt["id"], position_id, board, played)
    return result


def _alternatives(db, attempt_id, position_id, board, played):
    rows = db.connection.execute(
        "SELECT rank,line_json FROM deep_analysis_alternatives WHERE attempt_id=? ORDER BY rank",
        (attempt_id,),
    ).fetchall()
    result = []
    for row in rows:
        line = _decode(row["line_json"])
        if isinstance(line, dict) and line.get("position_id") == position_id:
            try:
                result.append({"rank": row["rank"], "line": view_line(line, board, played)})
            except (KeyError, TypeError, ValueError):
                continue
    return result


def _decode(value):
    try:
        return json.loads(value) if value is not None else None
    except (TypeError, ValueError):
        return None
