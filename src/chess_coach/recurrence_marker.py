"""Compare material-family source markers, sharing immutable game inputs per request."""

import json

from .fact_fingerprint import canonical, digest
from .material_source_rows import alternatives, completed, deep_row, lines, runs
from .pipeline_inputs import game_input


def game_parts(db, game_id):
    stage = db.connection.execute(
        "SELECT * FROM pipeline_stages WHERE game_id=? AND stage=?", (game_id, "analysis")
    ).fetchone()
    if stage is None or stage["status"] != "complete" or stage["output_id"] is None:
        raise ValueError("source unavailable")
    return {
        "game": game_input(db, game_id),
        "cheap_stage": dict(stage),
        "cheap_lines": lines(db.connection, stage["output_id"]),
    }


def marker(db, row, parts):
    conn = db.connection
    cheap_id = parts["cheap_stage"]["output_id"]
    deep = completed(deep_row(conn, row["position_id"], row["game_id"], row["subject"]))
    ids = [cheap_id, deep["analysis_run_id"]] if deep else [cheap_id]
    payload = {
        **parts,
        "deep": dict(deep) if deep else None,
        "runs": runs(conn, ids),
        "deep_lines": lines(conn, ids[-1]) if deep else [],
        "deep_alternatives": alternatives(conn, deep["attempt_id"]) if deep else [],
    }
    return digest(canonical(payload))


def source_state(db, row, fact, parts):
    try:
        stored = db.connection.execute(
            "SELECT input_json FROM detector_runs WHERE id=?", (fact["detector_run_id"],)
        ).fetchone()
        expected = json.loads(stored[0])["detector_input"]["source_marker"]
        return "marker matches" if expected == marker(db, row, parts) else "stale"
    except (KeyError, TypeError, ValueError, IndexError):
        return "stale"


def material_state(db, row, fact, parts):
    try:
        if row["game_id"] not in parts:
            parts[row["game_id"]] = game_parts(db, row["game_id"])
        return source_state(db, row, fact, parts[row["game_id"]])
    except (ValueError, TypeError, KeyError):
        return "stale"


def fork_state(db, row, fact, parts):
    stored = db.connection.execute(
        "SELECT input_json FROM detector_runs WHERE id=?", (fact["detector_run_id"],)
    ).fetchone()
    try:
        inputs = json.loads(stored[0])["detector_input"]
        if "source_marker" not in inputs:
            return "currentness unverified"
    except (ValueError, TypeError, KeyError, IndexError):
        return "currentness unverified"
    state = material_state(db, row, fact, parts)
    return "marker matches; proof not replayed" if state == "marker matches" else state
