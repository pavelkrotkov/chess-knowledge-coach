"""Persist attempt and job transitions as part of a caller-owned transaction."""

from .fact_fingerprint import canonical


def mark_stale(db, job, attempt_id):
    finish_state(db, job["id"], attempt_id, "stale", "selection_changed", "unknown", None, None)
    return {
        "job_id": job["id"],
        "position_id": job["position_id"],
        "status": "stale",
        "comparison": "unknown",
        "detail": "selection_changed",
    }


def finish_state(db, job_id, attempt_id, status, detail, comparison, run_id, result):
    best = canonical(result["best_work"]) if result is not None else None
    played = canonical(result["played_work"]) if result is not None else None
    updated = db.connection.execute(
        """UPDATE deep_analysis_attempts SET status=?,detail=?,comparison=?,analysis_run_id=?,
        best_work_json=?,played_work_json=?,finished_at=CURRENT_TIMESTAMP
        WHERE id=? AND job_id=? AND status='running'""",
        (status, detail, comparison, run_id, best, played, attempt_id, job_id),
    )
    if updated.rowcount != 1:
        raise ValueError("deep attempt is no longer running")
    updated = db.connection.execute(
        "UPDATE deep_analysis_jobs SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='running'",
        (status, job_id),
    )
    if updated.rowcount != 1:
        raise ValueError("deep job is no longer running")
