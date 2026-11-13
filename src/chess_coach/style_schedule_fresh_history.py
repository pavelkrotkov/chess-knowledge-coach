"""Read bounded freshness history for the current candidate sample."""

import sqlite3

from .purpose_config import PURPOSE
from .style_schedule_clock import reached
from .style_schedule_fresh_alias import used


def _history(db, key, positions, identities):
    position_marks = ",".join("?" for _ in positions)
    requests = db.connection.execute(
        f"""SELECT DISTINCT position_id FROM purpose_analysis_requests
        WHERE learner_key=? AND purpose=? AND position_id IN ({position_marks})""",
        (key, PURPOSE, *positions),
    ).fetchall()
    queued = db.connection.execute(
        f"""SELECT DISTINCT s.position_id FROM style_schedule_slots s
        JOIN style_schedule_cycles c ON c.id=s.cycle_id
        WHERE c.learner_key=? AND s.position_id IN ({position_marks})
          AND s.status IN ('ready','pending','running','interrupted')""",
        (key, *positions),
    ).fetchall()
    return {row[0] for row in requests + queued}, used(db, key, identities)


def read(db, key, positions, identities):
    if reached():
        return None
    db.connection.set_progress_handler(lambda: int(reached()), 1000)
    try:
        result = _history(db, key, positions, identities)
        return None if reached() else result
    except sqlite3.OperationalError as error:
        if getattr(error, "sqlite_errorcode", None) != sqlite3.SQLITE_INTERRUPT or not reached():
            raise
        return None
    finally:
        db.connection.set_progress_handler(None, 0)
