"""Read complete checkpoint-owned analysis rows for a game."""

import json

from .pipeline_output import output_is_current


def current_analysis(db, game_id):
    stage = db.connection.execute(
        "SELECT * FROM pipeline_stages WHERE game_id=? AND stage='analysis' AND status='complete'",
        (game_id,),
    ).fetchone()
    if stage is None or not output_is_current(db.connection, stage):
        raise ValueError("current cheap analysis is unavailable")
    run = db.connection.execute(
        "SELECT * FROM analysis_runs WHERE id=? AND game_id=?", (stage["output_id"], game_id)
    ).fetchone()
    if run is None:
        raise ValueError("current cheap analysis is unavailable")
    try:
        config = json.loads(run["config_json"])
    except (ValueError, TypeError):
        raise ValueError("current cheap analysis configuration is unavailable") from None
    if not isinstance(config, dict):
        raise ValueError("current cheap analysis configuration is unavailable")
    return stage, run, config


def analysis_lines(db, run_id, game_id):
    rows = db.connection.execute(
        """SELECT d.*, p.ply FROM decision_analysis_lines d JOIN positions p ON p.id=d.position_id
        WHERE d.run_id=? AND p.game_id=? ORDER BY p.ply,d.role""",
        (run_id, game_id),
    ).fetchall()
    return [dict(row) for row in rows]
