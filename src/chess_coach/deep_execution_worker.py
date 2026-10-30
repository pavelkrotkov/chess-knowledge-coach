"""Resume bounded deep work without locking the sync pipeline."""

from .db import Database
from .deep_execution_config import DeepOptions, prepare_config
from .deep_execution_engine import start_engine, stop_engine
from .deep_execution_lock import deep_lock
from .deep_execution_queue import recover_jobs
from .deep_execution_run import run_jobs
from .deep_execution_selection import current_selection
from .purpose_deadline import cleanup_timeout, startup_timeout


def run_deep(
    db: Database,
    selection_id: int,
    *,
    learner: str,
    options: DeepOptions | None = None,
    deadline=None,
):
    options = options or DeepOptions()
    if db.connection.in_transaction:
        raise RuntimeError("deep execution requires an idle database")
    with deep_lock(db.path):
        recover_jobs(db)
        selection = current_selection(db, selection_id, learner)
        binary, _, config = prepare_config(db, selection["game_id"], options)
        timeout = startup_timeout(deadline) if deadline is not None else 5.0
        if timeout is None:
            return {"status": "partial", "detail": "worker_deadline", "processed": []}
        engine, metadata = start_engine(binary, config, timeout=timeout)
        try:
            result = run_jobs(
                db, selection_id, learner, options, binary, engine, metadata, config, deadline
            )
        finally:
            if deadline is not None:
                engine.timeout = cleanup_timeout(deadline)
            stopped = stop_engine(engine)
        if not stopped:
            result["status"] = "partial"
            result["detail"] = "engine_shutdown_failed"
        return result
