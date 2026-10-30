"""Run one existing target/control purpose job."""

from .purpose_request import create
from .purpose_worker import run
from .style_schedule_budget import BudgetExceeded
from .style_schedule_recovery import abandon
from .style_schedule_slots import update_slot
from .style_schedule_work import attempt_count, new_work


def process_standard(db, config, slot, deadline):
    request_id = slot["request_id"]
    try:
        if request_id is None:
            request_id = create(
                db, slot["position_id"], config.learner, engine_path=config.engine_path
            )["request_id"]
            update_slot(db, slot["id"], "pending", "queued", request_id)
        update_slot(db, slot["id"], "running", "worker_claimed", request_id)
        before = attempt_count(db, request_id)
        result = run(
            db, request_id, config.learner, retry=slot["status"] == "interrupted", deadline=deadline
        )
    except BudgetExceeded as error:
        state = "unknown" if abandon(db, request_id, config.learner) else "running"
        detail = (
            "worker_deadline" if str(error) == "worker deadline" else "history_budget_exhausted"
        )
        update_slot(db, slot["id"], state, detail, request_id)
        return {"slot": slot["kind"], "status": "unknown", "detail": detail}
    except (ValueError, RuntimeError, OSError):
        update_slot(db, slot["id"], "unknown", "source_or_worker_unavailable", request_id)
        return {"slot": slot["kind"], "status": "unknown", "detail": "source_or_worker_unavailable"}
    status = result["status"]
    detail = result.get("detail", status)
    update_slot(db, slot["id"], status, detail, request_id)
    return {
        "slot": slot["kind"],
        "status": status,
        "detail": detail,
        "request_id": request_id,
        "work": new_work(db, request_id, before),
    }
