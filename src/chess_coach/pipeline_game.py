"""Advance the bounded stages of one game."""

from .mapping_transaction import mapping_transaction
from .pipeline_budget import position_count
from .pipeline_checkpoint import checkpoint
from .pipeline_opening import run_opening
from .pipeline_work import run_analysis, run_structures, run_tactical


def process_game(db, game_id, game_hash, config, engine_hash):
    try:
        if game_hash is None:
            raise ValueError("game input is unavailable")
        prior = db.connection.execute(
            'SELECT 1 FROM pipeline_stages WHERE game_id=? AND stage="input" AND status="failed"',
            (game_id,),
        ).fetchone()
        if prior is not None:
            with mapping_transaction(db):
                checkpoint(db.connection, game_id, "input", game_hash, "complete", "ok")
        return _advance_game(db, game_id, game_hash, config, engine_hash)
    except Exception:
        if db.connection.in_transaction:
            db.connection.rollback()
        with mapping_transaction(db):
            checkpoint(
                db.connection, game_id, "input", "unavailable", "failed", "game_processing_failed"
            )
        return {
            "game_id": game_id,
            "status": "failed",
            "detail": "game_processing_failed",
            "stages": [],
        }


def _advance_game(db, game_id, game_hash, config, engine_hash):
    count = position_count(db, game_id)
    if count > config.max_positions:
        with mapping_transaction(db):
            checkpoint(
                db.connection, game_id, "limits", game_hash, "failed", "position_budget_exceeded"
            )
        return {
            "game_id": game_id,
            "status": "failed",
            "detail": "position_budget_exceeded",
            "stages": [],
        }
    prior_limit = db.connection.execute(
        'SELECT 1 FROM pipeline_stages WHERE game_id=? AND stage="limits"', (game_id,)
    ).fetchone()
    if prior_limit is not None:
        with mapping_transaction(db):
            checkpoint(db.connection, game_id, "limits", game_hash, "complete", "ok")
    analysis = run_analysis(db, game_id, game_hash, config, engine_hash)
    stages = [
        analysis,
        run_structures(db, game_id, game_hash, config),
        run_opening(db, game_id, game_hash, config),
        run_tactical(db, game_id, game_hash, config, analysis),
    ]
    status = "complete" if all(stage["status"] == "complete" for stage in stages) else "partial"
    return {"game_id": game_id, "status": status, "stages": stages}
