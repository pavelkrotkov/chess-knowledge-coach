"""Check currentness and known failures for a recent ordinary game."""

from .pipeline_budget import position_count
from .pipeline_checkpoint import current
from .pipeline_inputs import analysis_input, game_input


def eligible(db, game, config, engine_hash):
    game_id = game["id"]
    if position_count(db, game_id) > config.max_positions:
        return None, "over_budget"
    failed = db.connection.execute(
        'SELECT stage,input_hash FROM pipeline_stages WHERE game_id=? AND status="failed" '
        'AND stage IN ("input","analysis")',
        (game_id,),
    ).fetchall()
    if any(row["stage"] == "input" for row in failed):
        return None, "failed"
    game_hash = game_input(db, game_id)
    key = analysis_input(game_hash, config, engine_hash)
    if any(row["stage"] == "analysis" and row["input_hash"] == key for row in failed):
        return None, "failed"
    if current(db.connection, game_id, "analysis", key) is not None:
        return None, "current"
    return (game_id, game_hash), "selected"
