"""Determine whether one eligible game needs bounded processing."""

from .db import Database
from .learner_identity import learner_color
from .pipeline_budget import position_count
from .pipeline_checkpoint import current
from .pipeline_config import PipelineConfig
from .pipeline_inputs import (
    analysis_input,
    game_input,
    opening_stage_input,
    structure_input,
    tactical_input,
)


def pending_game(db, game, config, engine_hash):
    if learner_color(game, config.learner) is None:
        return None
    count = position_count(db, game["id"])
    if count > config.max_positions:
        return game["id"], f"over-budget:{count}:{config.max_positions}"
    key = game_input(db, game["id"])
    failed = db.connection.execute(
        'SELECT 1 FROM pipeline_stages WHERE game_id=? AND stage IN ("input","limits") AND status="failed"',
        (game["id"],),
    ).fetchone()
    return (
        (game["id"], key)
        if failed or needs_work(db, game["id"], key, config, engine_hash)
        else None
    )


def needs_work(
    db: Database, game_id: int, game_hash: str, config: PipelineConfig, engine_hash: str | None
) -> bool:
    connection = db.connection
    analysis_key = analysis_input(game_hash, config, engine_hash)
    analysis = current(connection, game_id, "analysis", analysis_key)
    if analysis is None:
        return True
    opening_key, _ = opening_stage_input(db, game_id, config, game_hash)
    keys = (
        ("structures", structure_input(game_hash, config)),
        ("opening", opening_key),
        ("tactical", tactical_input(db, game_id, game_hash, config, analysis["output_id"])),
    )
    return any(current(connection, game_id, name, key) is None for name, key in keys)
