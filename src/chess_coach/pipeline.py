"""Bounded restartable game processing without automatic human review."""

import time

from .db import Database
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
        start_run(db)
        try:
            result = _run_pipeline(db, config, token, transport, clock)
        except Exception:
            finish_run(db, "failed")
            return {"status": "failed", "detail": "processing_failed"}
        finish_run(db, result["status"])
        if result["status"] != "failed":
            after_pipeline(db, config.learner, started)
        return result
