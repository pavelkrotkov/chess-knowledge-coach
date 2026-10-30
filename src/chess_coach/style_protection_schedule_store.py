"""Persist and query independently bound protection allocations."""

from .fact_fingerprint import canonical
from .style_protection_schedule_rotation import advance
from .style_protection_schedule_schema import validate


def insert(db, cycle, key, item, binding, reason, slot_ids, slots):
    validate(db.connection)
    slot_id = _overlap(item, slots, slot_ids)
    status = "unknown" if binding is None else "waiting_overlap" if slot_id else "ready"
    db.connection.execute(
        """INSERT INTO style_protection_allocations
        (cycle_id,game_id,position_id,evidence_id,binding_json,slot_id,status,detail)
        VALUES(?,?,?,?,?,?,?,?)""",
        (
            cycle,
            item["game_id"] if item else None,
            item["position_id"] if item else None,
            binding["evidence_id"] if binding else None,
            canonical(binding) if binding else None,
            slot_id,
            status,
            reason,
        ),
    )
    if item is not None:
        advance(db, key, item["game_id"])


def _overlap(item, slots, slot_ids):
    if item is None:
        return None
    for kind, existing in slots:
        if existing and existing["position_id"] == item["position_id"]:
            return slot_ids[kind]
    return None


def pending(db, learner_key):
    return db.connection.execute(
        """SELECT p.*,c.sequence FROM style_protection_allocations p
        JOIN style_schedule_cycles c ON c.id=p.cycle_id WHERE c.learner_key=?
        AND p.status IN ('ready','pending','running','interrupted') AND p.slot_id IS NULL
        ORDER BY c.sequence LIMIT 3""",
        (learner_key,),
    ).fetchall()


def pending_count(db, learner_key):
    return db.connection.execute(
        """SELECT COUNT(*) FROM style_protection_allocations p
        JOIN style_schedule_cycles c ON c.id=p.cycle_id WHERE c.learner_key=?
        AND p.status IN ('ready','pending','running','interrupted','waiting_overlap')""",
        (learner_key,),
    ).fetchone()[0]


def update(db, allocation_id, status, detail, request_id=None):
    row = db.connection.execute(
        "SELECT request_id FROM style_protection_allocations WHERE id=?", (allocation_id,)
    ).fetchone()
    if row is None or (row[0] is not None and request_id is not None and row[0] != request_id):
        raise ValueError("protection request binding changed")
    with db.connection:
        db.connection.execute(
            """UPDATE style_protection_allocations SET status=?,detail=?,
            request_id=COALESCE(request_id,?) WHERE id=?""",
            (status, detail, request_id, allocation_id),
        )
