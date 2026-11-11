"""Fingerprint the exact current material inputs, including absent analysis."""

import json

from .deep_selection_source import learner_key
from .fact_fingerprint import canonical, digest
from .material_source_marker import source_marker
from .material_source_rows import deep_row


def _runs(connection, stage, deep):
    ids = [stage["output_id"] if stage else None, deep["analysis_run_id"] if deep else None]
    return [
        dict(row)
        for run_id in ids
        if run_id is not None
        for row in connection.execute("SELECT * FROM analysis_runs WHERE id=?", (run_id,))
    ]


def _consumed(db, game_id, position_id, learner):
    try:
        return source_marker(db, position_id, game_id, learner)
    except (ValueError, TypeError, KeyError):
        return None


def marker(db, game_id, position_id, learner):
    connection = db.connection
    stage = connection.execute(
        "SELECT * FROM pipeline_stages WHERE game_id=? AND stage='analysis'", (game_id,)
    ).fetchone()
    deep = deep_row(connection, position_id, game_id, learner)
    game = connection.execute("SELECT time_control FROM games WHERE id=?", (game_id,)).fetchone()
    if game is None:
        raise ValueError("game unavailable")
    # An absent stage has its own fingerprint, so its first arrival expires the result.
    return digest(
        canonical(
            [
                dict(stage) if stage else None,
                dict(deep) if deep else None,
                _runs(connection, stage, deep),
                _consumed(db, game_id, position_id, learner),
                game["time_control"],
                learner_key(learner),
            ]
        )
    )


def configuration(db, prepared):
    provenance = prepared["provenance"]
    row = db.connection.execute(
        "SELECT engine,engine_version,config_json,binary_version,nnue,compatibility_json "
        "FROM analysis_runs WHERE id=?",
        (provenance["run_id"],),
    ).fetchone()
    if row is None or not row["engine"] or not row["engine_version"]:
        raise ValueError("analysis identity unavailable")
    config = json.loads(row["config_json"])
    if not isinstance(config, dict) or not config.get("engine_sha256"):
        raise ValueError("analysis configuration unavailable")
    deep = deep_row(
        db.connection, prepared["position_id"], prepared["game_id"], prepared["context"]["subject"]
    )
    job = deep["job_config"] if provenance["kind"] == "deep" and deep else None
    return digest(canonical([provenance["kind"], dict(row), job]))
