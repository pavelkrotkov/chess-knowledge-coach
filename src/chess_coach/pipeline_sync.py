"""Translate sync results to bounded, sanitized worker status."""

from .pipeline_network import BudgetExceeded, sync_games
from .pipeline_network_deadline import WorkerContextError


def sync_result(db, config, token, transport):
    try:
        result = sync_games(db, config, token=token, transport=transport)
        return {
            "status": "complete"
            if result["recent_complete"]
            and result["history_complete"]
            and not result["blocked_saturated"]
            else "partial",
            "games": result["games"],
            "requests": result["http_requests"],
            "bytes": result["http_bytes"],
            "windows": result["requests"],
            "recent_complete": result["recent_complete"],
            "history_complete": result["history_complete"],
            "blocked_saturated": result["blocked_saturated"],
        }
    except WorkerContextError:
        return {"status": "failed", "detail": "worker_process_required"}
    except BudgetExceeded:
        return {"status": "partial", "detail": "network_budget_exhausted"}
    except Exception:
        return {"status": "failed", "detail": "sync_failed"}
