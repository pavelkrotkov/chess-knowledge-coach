"""Read one protection allocation with fresh proof and request checks."""

from .style_protection_schedule_budget import resolution_budget
from .style_protection_schedule_schema import validate
from .style_protection_schedule_status_fields import provenance, request_state
from .style_protection_schedule_use import source_issue
from .style_schedule_budget import BudgetExceeded, history_budget


def status(db, learner, cycle_id, *, views=None, checks=None):
    validate(db.connection)
    row = db.connection.execute(
        "SELECT * FROM style_protection_allocations WHERE cycle_id=?", (cycle_id,)
    ).fetchone()
    if row is None:
        return {"state": "unknown", "detail": "allocation_missing", "allocations": ["protection"]}
    result = {
        "state": row["status"],
        "detail": row["detail"],
        "request_id": row["request_id"],
        "overlap": row["slot_id"] is not None,
        "allocations": ["control", "protection"] if row["slot_id"] else ["protection"],
    }
    if row["binding_json"] is None:
        return result
    if checks is not None:
        return {
            **result,
            **checks.get(row["id"], {"state": "unknown", "detail": "not_revalidated_in_report"}),
        }
    try:
        with history_budget() as history, resolution_budget() as proof:
            issue = source_issue(db, learner, row)
            if issue:
                return {
                    **result,
                    "state": "unknown",
                    "detail": issue,
                    "history_used": history["used"],
                    "proof_used": proof["used"],
                }
            result.update(provenance(row))
            result.update(request_state(db, learner, row, views))
            result.update(
                {
                    "history_used": history["used"],
                    "proof_used": proof["used"],
                    "proof_limit": proof["limit"],
                }
            )
            return result
    except (BudgetExceeded, ValueError, TypeError, KeyError):
        return {**result, "state": "unknown", "detail": "source_or_history_unavailable"}
