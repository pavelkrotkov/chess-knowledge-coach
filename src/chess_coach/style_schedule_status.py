"""Read current purpose scheduling coverage without writing or searching."""

import json

from .deep_selection_source import learner_key
from .purpose_view import show
from .style_schedule_schema import validate_style_schedule


def status(db, learner):
    validate_style_schedule(db.connection)
    key = learner_key(learner)
    cycle = db.connection.execute(
        "SELECT * FROM style_schedule_cycles WHERE learner_key=? ORDER BY sequence DESC LIMIT 1",
        (key,),
    ).fetchone()
    if cycle is None:
        return {"state": "not_scheduled", "slots": [], "pending": 0}
    rows = db.connection.execute(
        "SELECT * FROM style_schedule_slots WHERE cycle_id=? ORDER BY id", (cycle["id"],)
    ).fetchall()
    pending = db.connection.execute(
        """SELECT COUNT(*) FROM style_schedule_slots s
        JOIN style_schedule_cycles c ON c.id=s.cycle_id
        WHERE c.learner_key=? AND s.status IN ('ready','pending','running','interrupted')""",
        (key,),
    ).fetchone()[0]
    return {
        "state": "current",
        "cycle": cycle["sequence"],
        "coverage": json.loads(cycle["coverage_json"]),
        "slots": [_slot(db, learner, row) for row in rows],
        "pending": pending,
    }


def _slot(db, learner, row):
    result = {
        "kind": row["kind"],
        "status": row["status"],
        "detail": row["detail"],
        "request_id": row["request_id"],
    }
    if row["request_id"] is None:
        return result
    try:
        view = show(db, row["request_id"], learner)
    except ValueError:
        return {**result, "source_state": "unavailable"}
    state = view["status"]
    if state == "complete" and view["attempts"]:
        state = view["attempts"][-1]["status"]
    return {
        **result,
        "source_state": view["source_state"],
        "status": "stale" if view["source_state"] == "stale" else state,
    }
