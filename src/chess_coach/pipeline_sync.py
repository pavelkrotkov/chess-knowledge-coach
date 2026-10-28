"""Translate sync results to bounded, sanitized worker status."""

from .pipeline_cooldown import active_deadline
from .pipeline_network import BudgetExceeded, sync_games
from .pipeline_network_deadline import WorkerContextError, validate_worker_context
from .pipeline_sync_summary import sync_summary


def sync_result(db, config, token, transport, clock):
    try:
        validate_worker_context()
        waiting = _waiting(db, clock)
        if waiting is not None:
            return waiting
        result = sync_games(db, config, token=token, transport=transport, clock=clock)
        return sync_summary(result)
    except WorkerContextError:
        return {"status": "failed", "detail": "worker_process_required"}
    except BudgetExceeded:
        return _waiting(db, clock) or {"status": "partial", "detail": "network_budget_exhausted"}
    except Exception:
        return _waiting(db, clock) or {"status": "failed", "detail": "sync_failed"}


def _waiting(db, clock):
    deadline = active_deadline(db, clock)
    return (
        {"status": "waiting", "detail": "server_backoff", "retry_until": deadline}
        if deadline
        else None
    )
