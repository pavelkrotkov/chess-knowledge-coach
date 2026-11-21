"""Recheck the complete accepted history and terminal legal chess move."""

from .unified_training_proof import proof


def terminal(db, row, event_id):
    event = db.connection.execute(
        """SELECT event_id,kind,submitted_move FROM unified_session_events
        WHERE attempt_id=? ORDER BY rowid DESC LIMIT 1""",
        (row["attempt_id"],),
    ).fetchone()
    if event is None or row["status"] not in ("objective_verified", "line_completed"):
        raise ValueError("training attempt is not terminal")
    _check_event(event, event_id)
    hints = db.connection.execute(
        """SELECT COUNT(*) FROM unified_session_events
        WHERE attempt_id=? AND kind='hint'""",
        (row["attempt_id"],),
    ).fetchone()[0]
    if row["hints_used"] != hints or row["next_index"] != 1 or not row["finished_at"]:
        raise ValueError("attempt history does not match")
    return event, proof(row, event), bool(hints)


def _check_event(event, event_id):
    if event["kind"] != "move" or (event_id is not None and event_id != event["event_id"]):
        raise ValueError("terminal event does not match")
