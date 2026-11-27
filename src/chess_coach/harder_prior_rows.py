"""Load the two exact prior attempts recorded at a harder admission."""


def load(db, subject, earlier, recent):
    if not all(isinstance(value, str) and value for value in (earlier, recent)):
        raise ValueError("harder lineage unavailable")
    if earlier == recent:
        raise ValueError("harder lineage unavailable")
    rows = [
        db.connection.execute(
            "SELECT * FROM unified_sessions WHERE subject=? AND attempt_id=?", (subject, attempt)
        ).fetchone()
        for attempt in (earlier, recent)
    ]
    if any(row is None for row in rows):
        raise ValueError("harder lineage unavailable")
    return rows
