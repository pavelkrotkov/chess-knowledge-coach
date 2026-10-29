"""Resolve current deep job status without exposing identity fingerprints."""

from .deep_execution_view_lines import run_view
from .deep_execution_view_validation import result_is_presentable
from .deep_selection_source import learner_key
from .deep_selection_views import show_selection


def deep_for_position(db, position_id, learner, board, played, *, _history=None):
    key = _safe_key(learner)
    if key is None:
        return None
    job = db.connection.execute(
        """SELECT j.*, s.game_id FROM deep_analysis_current c
        JOIN deep_analysis_jobs j ON j.id=c.job_id
        JOIN deep_selection_runs s ON s.id=j.selection_id
        JOIN deep_selection_current sc ON sc.selection_id=s.id
        WHERE c.position_id=? AND s.learner_key=? ORDER BY j.id DESC LIMIT 1""",
        (position_id, key),
    ).fetchone()
    if job is None:
        return None
    if not _selection_is_current(db, job, learner, position_id, _history):
        return {
            "job_id": job["id"],
            "status": "stale",
            "detail": "selection_changed",
            "result": None,
        }
    attempt = db.connection.execute(
        "SELECT * FROM deep_analysis_attempts WHERE job_id=? ORDER BY attempt_number DESC LIMIT 1",
        (job["id"],),
    ).fetchone()
    result = run_view(db, attempt, position_id, board, played) if attempt else None
    return _present(job, attempt, result, board)


def _selection_is_current(db, job, learner, position_id, history):
    try:
        selection = show_selection(
            db,
            job["game_id"],
            learner,
            selection_id=job["selection_id"],
            _history=history,
            _position_id=position_id,
        )
    except ValueError:
        return False
    return selection["state"] == "current"


def _safe_key(learner):
    try:
        return learner_key(learner)
    except ValueError:
        return None


def _present(job, attempt, result, board):
    status = job["status"]
    invalid = status in {"complete", "unstable"} and not result_is_presentable(result, board)
    return {
        "job_id": job["id"],
        "selection_id": job["selection_id"],
        "status": "insufficient" if invalid else status,
        "detail": "stored_result_incomplete"
        if invalid
        else attempt["detail"]
        if attempt
        else "pending",
        "comparison": "unknown" if invalid else attempt["comparison"] if attempt else "unknown",
        "attempt_number": attempt["attempt_number"] if attempt else None,
        "result": result,
    }
