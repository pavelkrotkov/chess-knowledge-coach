"""Persist and read existing target/control slots without changing their contract."""

from .deep_selection_source import learner_key


def insert_slot(db, cycle_id, kind, item):
    if item is None:
        item = {
            "game_id": None,
            "position_id": None,
            "status": "unknown",
            "detail": "target_not_found_in_scanned_sample"
            if kind == "target"
            else "control_not_found_in_scanned_sample",
        }
    cursor = db.connection.execute(
        """INSERT INTO style_schedule_slots(cycle_id,kind,game_id,position_id,status,detail)
        VALUES(?,?,?,?,?,?)""",
        (cycle_id, kind, item["game_id"], item["position_id"], item["status"], item["detail"]),
    )
    return cursor.lastrowid


def pending(db, learner):
    return db.connection.execute(
        """SELECT s.*,c.sequence FROM style_schedule_slots s JOIN style_schedule_cycles c ON c.id=s.cycle_id
        WHERE c.learner_key=? AND s.status IN ('ready','pending','running','interrupted')
        ORDER BY c.sequence,s.id LIMIT 3""",
        (learner_key(learner),),
    ).fetchall()


def update_slot(db, slot_id, status, detail, request_id=None):
    with db.connection:
        db.connection.execute(
            """UPDATE style_schedule_slots SET status=?,detail=?,request_id=COALESCE(?,request_id)
            WHERE id=?""",
            (status, detail, request_id, slot_id),
        )
