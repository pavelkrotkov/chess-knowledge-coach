"""Run one explicitly requested job under the shared deep-worker lock."""

import time

from .deep_execution_lock import deep_lock
from .purpose_attempts import finish
from .purpose_claim import claim
from .purpose_config import WORKER_SECONDS
from .purpose_execute import execute


def run(db, request_id, learner, *, retry=False):
    if type(retry) is not bool or db.connection.in_transaction:
        raise ValueError("invalid purpose worker invocation")
    deadline = time.monotonic() + WORKER_SECONDS
    with deep_lock(db.path):
        item, state = claim(db, request_id, learner, retry=retry)
        if item is None:
            return {"request_id": request_id, "status": state}
        _row, snapshot, config = item
        try:
            status, detail, result = execute(db, snapshot, config, deadline)
        except Exception:
            status, detail, result = "insufficient", "engine_or_processing_failure", {}
        result["worker_seconds_limit"] = WORKER_SECONDS
        result["worker_seconds_elapsed"] = round(time.monotonic() - (deadline - WORKER_SECONDS), 3)
        return finish(db, request_id, learner, status, detail, result)
