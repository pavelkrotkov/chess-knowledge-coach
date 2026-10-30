"""Execute durable purpose slots without changing ordinary deep state."""

import time

from .deep_selection_source import learner_key
from .style_protection_schedule_budget import resolution_budget
from .style_protection_schedule_overlap import reconcile
from .style_protection_schedule_store import pending_count
from .style_schedule_budget import history_budget
from .style_schedule_dispatch import dispatch
from .style_schedule_queue import pending
from .style_schedule_store import create_cycle
from .style_schedule_work_summary import summary


def process_schedule(db, config, *, deadline):
    with history_budget(deadline=deadline) as budget, resolution_budget() as proof_budget:
        cycle = create_cycle(db, config.learner)
        reconcile(db, config.learner)
        processed = []
        for slot in pending(db, config.learner):
            if time.monotonic() >= deadline:
                break
            processed.append(dispatch(db, config, slot, deadline))
        return {
            "status": "partial"
            if pending(db, config.learner) or pending_count(db, learner_key(config.learner))
            else "complete",
            "cycle_id": cycle,
            "processed": processed,
            "history_used": budget["used"],
            "history_limit": budget["limit"],
            "protection_resolutions": dict(proof_budget),
            "native_work": summary(processed),
        }
