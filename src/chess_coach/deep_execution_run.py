"""Process a bounded set of existing normal deep jobs."""

from .deep_execution_claim import claim_job
from .deep_execution_queue import pending_jobs, prepare_jobs
from .deep_execution_report import execution_report
from .deep_execution_selection import current_selection
from .deep_execution_task import execute_job


def run_jobs(db, selection_id, learner, options, binary, engine, metadata, config, deadline):
    prepare_jobs(db, selection_id, learner, config, options.retry_insufficient)
    processed = []
    for job in pending_jobs(db, selection_id, options.max_jobs):
        try:
            attempt_id = claim_job(db, job, learner)
        except ValueError:
            break
        item, broken = execute_job(
            db, job, attempt_id, learner, binary, engine, metadata, config, deadline=deadline
        )
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
