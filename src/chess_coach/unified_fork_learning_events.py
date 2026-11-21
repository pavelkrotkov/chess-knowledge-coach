"""Check the final recorded answer and all accepted fork assistance."""


def answer(db, row, event_id):
    event = db.connection.execute(
        """SELECT event_id,kind,submitted_move,created_at FROM unified_session_events
        WHERE attempt_id=? ORDER BY rowid DESC LIMIT 1""",
        (row["attempt_id"],),
    ).fetchone()
    if not event or event["kind"] != "move" or (event_id and event["event_id"] != event_id):
        raise ValueError("fork answer does not match")
    return event


def assistance(detail, observed):
    assisted = detail["assistance"] != "unassisted"
    if assisted != bool(observed["hints"]) or (
        observed["reveals"] and detail["assistance"] != "revealed"
    ):
        raise ValueError("fork assistance history unavailable")
    return assisted
