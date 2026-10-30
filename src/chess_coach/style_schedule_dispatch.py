"""Dispatch ordinary and shared-protection purpose jobs."""

from .style_protection_schedule_overlap import after as overlap_after
from .style_protection_schedule_overlap import before as overlap_before
from .style_protection_schedule_worker import process as process_protection
from .style_schedule_standard_worker import process_standard


def dispatch(db, config, slot, deadline):
    if slot["kind"] == "protection":
        return process_protection(db, config, slot, deadline)
    overlap = overlap_before(db, config.learner, slot)
    result = process_standard(db, config, slot, deadline)
    overlap_after(db, config.learner, overlap, slot["id"])
    labels = db.connection.execute(
        "SELECT 1 FROM style_protection_allocations WHERE slot_id=?", (slot["id"],)
    ).fetchone()
    result["allocations"] = [slot["kind"], "protection"] if labels else [slot["kind"]]
    return result
