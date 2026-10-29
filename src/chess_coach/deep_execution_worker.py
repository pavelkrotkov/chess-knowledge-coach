"""Resume bounded deep work without locking the sync pipeline."""

from .db import Database
from .deep_execution_claim import claim_job
from .deep_execution_config import DeepOptions, prepare_config
from .deep_execution_engine import start_engine, stop_engine
from .deep_execution_lock import deep_lock
from .deep_execution_queue import pending_jobs, prepare_jobs, recover_jobs
from .deep_execution_report import execution_report
from .deep_execution_selection import current_selection
from .deep_execution_task import execute_job


def run_deep(db: Database, selection_id: int, *, learner: str, options: DeepOptions | None = None):
    options = options or DeepOptions()
    if db.connection.in_transaction:
        raise RuntimeError("deep execution requires an idle database")
    with deep_lock(db.path):
        recover_jobs(db)
        selection = current_selection(db, selection_id, learner)
        binary, _, config = prepare_config(db, selection["game_id"], options)
        engine, metadata = start_engine(binary, config)
        try:
            result = _run(db, selection_id, learner, options, binary, engine, metadata, config)
        finally:
            stopped = stop_engine(engine)
        if not stopped:
            result["status"] = "partial"
            result["detail"] = "engine_shutdown_failed"
        return result


def _run(db, selection_id, learner, options, binary, engine, metadata, config):
    prepare_jobs(db, selection_id, learner, config, options.retry_insufficient)
    processed = []
    for job in pending_jobs(db, selection_id, options.max_jobs):
        try:
            attempt_id = claim_job(db, job, learner)
        except ValueError:
            break
        item, broken = execute_job(db, job, attempt_id, learner, binary, engine, metadata, config)
        processed.append(item)
        if broken or item["status"] == "stale":
            break
    report = execution_report(db, selection_id, processed)
    try:
        current_selection(db, selection_id, learner)
    except ValueError:
        report["status"] = "partial"
        report["detail"] = "selection_changed"
    return report
