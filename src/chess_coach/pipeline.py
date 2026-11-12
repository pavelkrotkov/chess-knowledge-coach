"""Bounded restartable game processing without automatic human review."""

import sqlite3
import time

from .capture_game_trend_scan import after_pipeline as capture_after_pipeline
from .db import Database
from .fork_game_trend_scan import after_pipeline as fork_after_pipeline
from .fork_miss_worker import after_pipeline as fork_miss_after_pipeline
from .opening_queue_worker import after_pipeline as opening_after_pipeline
from .opening_study_worker import after_pipeline as study_after_pipeline
from .pipeline_config import PipelineConfig
from .pipeline_cooldown import utc_now
from .pipeline_health import finish_run, start_run
from .pipeline_lock import pipeline_lock
from .pipeline_run import run_pipeline as _run_pipeline
from .short_mate_trend_scan import after_pipeline


def process_pipeline(
    db: Database, config: PipelineConfig, *, token: str | None = None, transport=None, clock=None
) -> dict:
    started = time.monotonic()
    config.validate()
    if clock is not None:
        utc_now(clock)
    if db.connection.in_transaction:
        raise RuntimeError("pipeline requires an idle database connection")
    with pipeline_lock(db.path):
        health_error = _health(start_run, db)
        if health_error:
            return _failure("start", health_error)
        phase = {"name": "initializing"}
        try:
            result = _run_pipeline(db, config, token, transport, clock, phase)
        except Exception as error:
            failure = _failure(phase["name"], _category(error))
            health_error = _health(finish_run, db, "failed")
            if health_error:
                failure["health_error_category"] = health_error
            return failure
        health_error = _health(finish_run, db, result["status"])
        if health_error:
            return _failure("finish", health_error)
        if result["status"] != "failed":
            after_pipeline(db, config.learner, started)
            capture_after_pipeline(db, config.learner, started)
            opening_after_pipeline(db, config, started)
            fork_after_pipeline(db, config.learner, started)
            fork_miss_after_pipeline(db, config.learner, started)
            study_after_pipeline(db, config.learner, started)
        return result


# Classify failures without exposing exception messages, SQL, or private sources.
def _category(error):
    if isinstance(error, sqlite3.Error):
        if getattr(error, "sqlite_errorcode", 0) & 255 == sqlite3.SQLITE_BUSY:
            return "sqlite_busy"
        return "sqlite_error"
    return "unexpected_error"


def _failure(phase, category):
    return {
        "status": "failed",
        "detail": "processing_failed",
        "phase": phase,
        "error_category": category,
    }


# Health writes are transactional. A SQLite failure is reported without
# replacing an earlier processing diagnosis or exposing the exception text.
def _health(action, *args):
    try:
        action(*args)
    except sqlite3.Error as error:
        return _category(error)
    return None
