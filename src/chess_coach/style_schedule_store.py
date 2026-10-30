"""Persist one deterministic recent-game scheduling cycle."""

from .deep_selection_source import learner_key
from .fact_fingerprint import canonical
from .style_schedule_budget import CURRENT
from .style_schedule_candidates import allocate
from .style_schedule_rotation import advance
from .style_schedule_schema import validate_style_schedule


def next_sequence(db, learner):
    validate_style_schedule(db.connection)
    key = learner_key(learner)
    row = db.connection.execute(
        "SELECT COALESCE(MAX(sequence),-1)+1 FROM style_schedule_cycles WHERE learner_key=?",
        (key,),
    ).fetchone()
    return key, row[0]


def create_cycle(db, learner):
    key, sequence = next_sequence(db, learner)
    budget = CURRENT.get()
    if budget is None:
        raise RuntimeError("scheduling requires a history budget")
    original_limit = budget["limit"]
    budget["limit"] = min(original_limit, budget["used"] + 500)
    try:
        coverage, slots = allocate(db, learner, key, sequence)
    finally:
        budget["limit"] = original_limit
    coverage["scan_history_units"] = budget["used"]
    coverage["scan_history_unit_limit"] = 500
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        cursor = db.connection.execute(
            "INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json) VALUES(?,?,?)",
            (key, sequence, canonical(coverage)),
        )
        for kind, item in slots:
            _insert_slot(db, cursor.lastrowid, kind, item)
            if item is not None:
                advance(db, key, kind, item["game_id"])
        db.connection.commit()
        return cursor.lastrowid
    except BaseException:
        db.connection.rollback()
        raise


def _insert_slot(db, cycle_id, kind, item):
    if item is None:
        item = {
            "game_id": None,
            "position_id": None,
            "status": "unknown",
            "detail": "target_not_found_in_scanned_sample"
            if kind == "target"
            else "control_not_found_in_scanned_sample",
        }
    db.connection.execute(
        """INSERT INTO style_schedule_slots(cycle_id,kind,game_id,position_id,status,detail)
        VALUES(?,?,?,?,?,?)""",
        (cycle_id, kind, item["game_id"], item["position_id"], item["status"], item["detail"]),
    )


def pending(db, learner):
    return db.connection.execute(
        """SELECT s.* FROM style_schedule_slots s JOIN style_schedule_cycles c ON c.id=s.cycle_id
        WHERE c.learner_key=? AND s.status IN ('ready','pending','running','interrupted')
        ORDER BY c.sequence,s.id LIMIT 2""",
        (learner_key(learner),),
    ).fetchall()


def update_slot(db, slot_id, status, detail, request_id=None):
    with db.connection:
        db.connection.execute(
            """UPDATE style_schedule_slots SET status=?,detail=?,request_id=COALESCE(?,request_id)
            WHERE id=?""",
            (status, detail, request_id, slot_id),
        )
