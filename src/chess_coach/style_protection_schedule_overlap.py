"""Attach a protection label to an existing control job without a second search."""

from .deep_selection_source import learner_key
from .style_protection_schedule_store import update
from .style_protection_schedule_use import source_issue, valid_request


def before(db, learner, slot):
    row = _for_slot(db, slot["id"])
    if row is None:
        return None
    issue = source_issue(db, learner, row)
    if issue:
        update(db, row["id"], "unknown", issue)
        return None
    update(db, row["id"], "running", "shared_control_claim")
    return row["id"]


def after(db, learner, allocation_id, slot_id):
    if allocation_id is None:
        return
    row = db.connection.execute(
        "SELECT * FROM style_protection_allocations WHERE id=?", (allocation_id,)
    ).fetchone()
    slot = db.connection.execute(
        "SELECT * FROM style_schedule_slots WHERE id=?", (slot_id,)
    ).fetchone()
    request_id = slot["request_id"]
    if request_id is None or not valid_request(db, learner, row, request_id):
        update(db, allocation_id, "unknown", "request_binding_unavailable")
    else:
        issue = source_issue(db, learner, row)
        if issue:
            update(db, allocation_id, "unknown", issue, request_id)
        else:
            update(db, allocation_id, slot["status"], slot["detail"], request_id)


def _for_slot(db, slot_id):
    return db.connection.execute(
        """SELECT * FROM style_protection_allocations WHERE slot_id=?
        AND status IN ('waiting_overlap','running','interrupted')""",
        (slot_id,),
    ).fetchone()


def reconcile(db, learner):
    rows = db.connection.execute(
        """SELECT p.id,p.slot_id FROM style_protection_allocations p
        JOIN style_schedule_slots s ON s.id=p.slot_id
        JOIN style_schedule_cycles c ON c.id=p.cycle_id
        WHERE c.learner_key=? AND p.status IN ('waiting_overlap','running','interrupted')
        AND s.status NOT IN ('ready','pending','running','interrupted')
        ORDER BY c.sequence LIMIT 3""",
        (learner_key(learner),),
    ).fetchall()
    for row in rows:
        after(db, learner, row["id"], row["slot_id"])
