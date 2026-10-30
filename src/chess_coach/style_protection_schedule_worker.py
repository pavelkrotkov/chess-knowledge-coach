"""Run a distinct protection-targeted candidate-set diagnostic."""

from .purpose_request import create
from .purpose_worker import run
from .style_protection_schedule_store import update
from .style_protection_schedule_use import source_issue, valid_request
from .style_schedule_budget import BudgetExceeded
from .style_schedule_recovery import abandon
from .style_schedule_work import attempt_count, new_work


def process(db, config, row, deadline):
    request_id = row["request_id"]
    try:
        issue = source_issue(db, config.learner, row)
        if issue:
            return _unknown(db, row, issue, request_id)
        if request_id is None:
            request_id = create(
                db, row["position_id"], config.learner, engine_path=config.engine_path
            )["request_id"]
        if not valid_request(db, config.learner, row, request_id):
            return _unknown(db, row, "request_binding_mismatch", request_id)
        update(db, row["id"], "running", "worker_claimed", request_id)
        before = attempt_count(db, request_id)
        result = run(
            db, request_id, config.learner, retry=row["status"] == "interrupted", deadline=deadline
        )
        issue = source_issue(db, config.learner, row)
        if issue:
            return _unknown(db, row, issue, request_id)
        status = result["status"]
        detail = result.get("detail", status)
        update(db, row["id"], status, detail, request_id)
        return {
            "slot": "protection",
            "status": status,
            "detail": detail,
            "request_id": request_id,
            "allocations": ["protection"],
            "work": new_work(db, request_id, before),
        }
    except BudgetExceeded:
        if not abandon(db, request_id, config.learner):
            update(db, row["id"], "running", "history_budget_exhausted", request_id)
            return {
                "slot": "protection",
                "status": "unknown",
                "detail": "history_budget_exhausted",
                "request_id": request_id,
            }
        return _unknown(db, row, "history_budget_exhausted", request_id)
    except (ValueError, RuntimeError, OSError):
        return _unknown(db, row, "source_or_worker_unavailable", request_id)


def _unknown(db, row, detail, request_id):
    update(db, row["id"], "unknown", detail, request_id)
    return {"slot": "protection", "status": "unknown", "detail": detail, "request_id": request_id}
