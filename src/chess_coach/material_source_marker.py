"""Fingerprint only the current game and the current analysis inputs consumed."""

from .fact_fingerprint import canonical, digest
from .material_source_rows import consumed_rows
from .pipeline_inputs import game_input


def source_marker(db, position_id, game_id, learner):
    connection = db.connection
    stage = connection.execute(
        "SELECT * FROM pipeline_stages WHERE game_id=? AND stage=?", (game_id, "analysis")
    ).fetchone()
    if stage is None or stage["status"] != "complete" or stage["output_id"] is None:
        raise ValueError("current cheap analysis unavailable")
    payload = {
        "game": game_input(db, game_id),
        "cheap_stage": dict(stage),
        **consumed_rows(connection, stage["output_id"], position_id, game_id, learner),
    }
    return digest(canonical(payload))
