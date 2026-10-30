"""Bound purpose provenance to the newest scheduled allocation cycles."""

from .deep_selection_source import learner_key

CYCLE_LIMIT = 100


def slots(db, learner):
    cycles = db.connection.execute(
        "SELECT id,sequence FROM style_schedule_cycles WHERE learner_key=? ORDER BY sequence DESC LIMIT ?",
        (learner_key(learner), CYCLE_LIMIT + 1),
    ).fetchall()
    retained = cycles[:CYCLE_LIMIT]
    if not retained:
        return [], {
            "examined_cycles": 0,
            "cycle_limit": CYCLE_LIMIT,
            "allocation_labels_examined": 0,
            "allocation_label_limit": 3 * CYCLE_LIMIT,
            "older_cycles_unknown": False,
        }
    ids = [row["id"] for row in retained]
    placeholders = ",".join("?" for _ in ids)
    rows = db.connection.execute(
        f"""SELECT s.*, c.sequence FROM style_schedule_slots s
        JOIN style_schedule_cycles c ON c.id=s.cycle_id
        WHERE s.cycle_id IN ({placeholders}) ORDER BY c.sequence DESC,s.id DESC""",
        ids,
    ).fetchall()
    protection = db.connection.execute(
        f"""SELECT p.*, c.sequence FROM style_protection_allocations p
        JOIN style_schedule_cycles c ON c.id=p.cycle_id
        WHERE p.cycle_id IN ({placeholders}) ORDER BY c.sequence DESC,p.id DESC""",
        ids,
    ).fetchall()
    rows = [dict(row) for row in rows] + [{**dict(row), "kind": "protection"} for row in protection]
    return rows, {
        "examined_cycles": len(retained),
        "allocation_labels_examined": len(rows),
        "allocation_label_limit": 3 * CYCLE_LIMIT,
        "cycle_limit": CYCLE_LIMIT,
        "older_cycles_unknown": len(cycles) > CYCLE_LIMIT,
    }
