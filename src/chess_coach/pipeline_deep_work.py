"""Reconcile the current bounded deep configuration for one game."""

import json

from .deep_execution_config import prepare_config
from .deep_execution_worker import run_deep
from .pipeline_deep_config import deep_options


def needs_execution(db, selection_id, config):
    rows = db.connection.execute(
        """SELECT j.status,j.config_json FROM deep_selection_items i
        LEFT JOIN deep_analysis_current c ON c.selection_id=i.selection_id AND c.position_id=i.position_id
        LEFT JOIN deep_analysis_jobs j ON j.id=c.job_id WHERE i.selection_id=?""",
        (selection_id,),
    ).fetchall()
    return any(_pending(row, config) for row in rows)


def _pending(row, config):
    if row["config_json"] is None or row["status"] in {"pending", "running", "stale"}:
        return True
    try:
        recorded = json.loads(row["config_json"])
    except (ValueError, TypeError):
        return True
    if not isinstance(recorded, dict):
        return True
    return any(recorded.get(key) != value for key, value in config.items())


def execute(db, game_id, selection_id, config, remaining, *, deadline=None):
    options = deep_options(config, max_jobs=remaining)
    _, _, recorded = prepare_config(db, game_id, options)
    if not needs_execution(db, selection_id, recorded):
        return {"status": "current", "processed": []}
    return run_deep(db, selection_id, learner=config.learner, options=options, deadline=deadline)
