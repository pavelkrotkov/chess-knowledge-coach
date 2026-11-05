"""Recheck played-time ownership and the complete ordinary analysis source."""

from .deep_selection_checkpoint import validate_checkpoint
from .deep_selection_source import MAX_DECISIONS
from .deep_selection_source_rows import current_analysis
from .pipeline_inputs import analysis_input, game_input
from .style_time_candidates import verified
from .style_time_query import load_game


def eligible(db, learner, item, config, engine_hash):
    game = load_game(db.connection, item["game_id"])
    if not verified(game, learner) or game["projected_start"] != item["started_at"]:
        return False
    if game["variant"] != "Standard":
        return False
    if db.connection.execute(
        "SELECT 1 FROM positions WHERE game_id=? LIMIT 1 OFFSET ?", (game["id"], MAX_DECISIONS)
    ).fetchone():
        return False
    stage, _run, source_config = current_analysis(db, game["id"])
    validate_checkpoint(db, game["id"], stage, source_config)
    expected = analysis_input(game_input(db, game["id"]), config, engine_hash)
    return stage["input_hash"] == expected
