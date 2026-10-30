"""Execute durable purpose slots without changing ordinary deep state."""

import time

from .purpose_request import create
from .purpose_worker import run
from .style_schedule_budget import BudgetExceeded, history_budget
from .style_schedule_recovery import abandon
from .style_schedule_store import create_cycle, pending, update_slot


def process_schedule(db, config, *, deadline):
    with history_budget(deadline=deadline) as budget:
        cycle = create_cycle(db, config.learner)
        processed = []
        for slot in pending(db, config.learner):
            if time.monotonic() >= deadline:
                break
            processed.append(_process(db, config, slot, deadline))
        return {
            "status": "partial" if pending(db, config.learner) else "complete",
            "cycle_id": cycle,
            "processed": processed,
            "history_used": budget["used"],
            "history_limit": budget["limit"],
        }


def _process(db, config, slot, deadline):
    request_id = slot["request_id"]
    try:
        if request_id is None:
            request_id = create(
                db, slot["position_id"], config.learner, engine_path=config.engine_path
            )["request_id"]
            update_slot(db, slot["id"], "pending", "queued", request_id)
        update_slot(db, slot["id"], "running", "worker_claimed", request_id)
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
    return {"slot": slot["kind"], "status": status, "detail": detail}
