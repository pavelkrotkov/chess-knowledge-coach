"""Bounded restartable game processing without automatic human review."""

from .db import Database
from .mastery import mastery_report
from .pipeline_config import PipelineConfig
from .pipeline_cursor import save_cursor
from .pipeline_game import process_game
from .pipeline_health import finish_run, record_sync, run_status, start_run
from .pipeline_inputs import engine_identity, scan_input
from .pipeline_lock import pipeline_lock
from .pipeline_pending import pending_games
from .pipeline_report import public_report
from .pipeline_sync import sync_result


def process_pipeline(
    db: Database, config: PipelineConfig, *, token: str | None = None, transport=None
) -> dict:
    config.validate()
    if db.connection.in_transaction:
        raise RuntimeError("pipeline requires an idle database connection")
    with pipeline_lock(db.path):
        start_run(db)
        try:
            result = _run_pipeline(db, config, token, transport)
        except Exception:
            finish_run(db, "failed")
            return {"status": "failed", "detail": "processing_failed"}
        finish_run(db, result["status"])
        return result


def _run_pipeline(db, config, token, transport):
    sync = sync_result(db, config, token, transport)
    record_sync(db, sync)
    if sync.get("detail") == "worker_process_required":
        return {"status": "failed", "sync": sync, "games": [], "mastery": []}
    engine_hash = engine_identity(config.engine_path)
    games = []
    pending, scan, cursor = pending_games(db, config, engine_hash)
    account, last_scanned, scan_hash = cursor
    for game_id, game_hash in pending:
        games.append(process_game(db, game_id, game_hash, config, engine_hash))
        save_cursor(db, account, game_id, scan_hash)
    save_cursor(db, account, last_scanned, scan_hash)
    scan["has_more"] |= scan_input(db, config, engine_hash) != scan_hash
    reports = mastery_report(db, subject=config.learner)
    status = run_status(db, sync, games, scan)
    return {
        "status": status,
        "sync": sync,
        "scan": scan,
        "games": games,
        "mastery": [public_report(row) for row in reports],
    }
