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
        return [], {"examined_cycles": 0, "cycle_limit": CYCLE_LIMIT, "older_cycles_unknown": False}
    ids = [row["id"] for row in retained]
    placeholders = ",".join("?" for _ in ids)
    rows = db.connection.execute(
        f"""SELECT s.*, c.sequence FROM style_schedule_slots s
        JOIN style_schedule_cycles c ON c.id=s.cycle_id
        WHERE s.cycle_id IN ({placeholders}) ORDER BY c.sequence DESC,s.id DESC""",
        ids,
    ).fetchall()
    return rows, {
        "examined_cycles": len(retained),
        "cycle_limit": CYCLE_LIMIT,
        "older_cycles_unknown": len(cycles) > CYCLE_LIMIT,
    }
