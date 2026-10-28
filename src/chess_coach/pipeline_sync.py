"""Translate sync results to bounded, sanitized worker status."""

from .mastery_time import parse_utc
from .pipeline_cooldown import active_deadline, stored_deadline, utc_now
from .pipeline_cooldown_expiry import clear_expired
from .pipeline_health import record_sync
from .pipeline_lock import pipeline_lock
from .pipeline_network import BudgetExceeded, sync_games
from .pipeline_network_deadline import WorkerContextError, validate_worker_context
from .pipeline_sync_summary import sync_summary


def sync_result(db, config, token, transport, clock, *, retry_only=False):
    with pipeline_lock(db.path, sync=True):
        deadline = stored_deadline(db)
        if retry_only and (deadline is None or parse_utc(deadline) > utc_now(clock)):
            return None
        result = _sync_result(db, config, token, transport, clock)
        clear_expired(db, clock, deadline, result)
        record_sync(db, result)
        return result


def _sync_result(db, config, token, transport, clock):
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
