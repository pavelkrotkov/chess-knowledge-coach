"""Read bounded freshness history for the current candidate sample."""

import sqlite3

from .purpose_config import PURPOSE
from .style_schedule_clock import reached


def _history(db, key, positions, games):
    position_marks = ",".join("?" for _ in positions)
    game_marks = ",".join("?" for _ in games)
    requests = db.connection.execute(
        f"""SELECT DISTINCT position_id FROM purpose_analysis_requests
        WHERE learner_key=? AND purpose=? AND position_id IN ({position_marks})""",
        (key, PURPOSE, *positions),
    ).fetchall()
    previous = db.connection.execute(
        f"""SELECT DISTINCT s.game_id FROM style_schedule_cycles c
        JOIN style_schedule_slots s ON s.cycle_id=c.id
        WHERE c.learner_key=? AND s.kind='control' AND c.sequence % 4=1
          AND s.game_id IN ({game_marks})
          AND json_extract(c.coverage_json,'$.early_center_policy')='early-center-v1'
          AND json_extract(c.coverage_json,'$.early_center_targeted')=1
          AND (s.request_id IS NOT NULL OR s.status IN ('ready','pending','running','interrupted'))""",
        (key, *games),
    ).fetchall()
    return {row[0] for row in requests}, {row[0] for row in previous}


def read(db, key, positions, games):
    if reached():
        return None
    db.connection.set_progress_handler(lambda: int(reached()), 1000)
    try:
        result = _history(db, key, positions, games)
        return None if reached() else result
    except sqlite3.OperationalError as error:
        if getattr(error, "sqlite_errorcode", None) != sqlite3.SQLITE_INTERRUPT or not reached():
            raise
        return None
    finally:
        db.connection.set_progress_handler(None, 0)
