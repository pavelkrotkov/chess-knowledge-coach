"""Read the bounded oldest and newest uncued recognition history."""

from .learner_identity import normalize_identity

LIMIT = 100


def _end(db, subject, order):
    return db.connection.execute(
        f"""SELECT a.*,e.action,e.answer,e.assisted,e.created_at AS answered_at
        FROM recognition_attempts a LEFT JOIN recognition_events e ON e.attempt_id=a.attempt_id
        WHERE a.subject=? ORDER BY a.started_at {order},a.attempt_id {order} LIMIT ?""",
        (normalize_identity(subject), LIMIT + 1),
    ).fetchall()


def rows(db, subject):
    oldest, newest = _end(db, subject, "ASC"), _end(db, subject, "DESC")
    combined = {row["attempt_id"]: row for row in oldest + newest}
    limited = len(combined) > 2 * LIMIT
    if limited:
        combined = {row["attempt_id"]: row for row in oldest[:LIMIT] + newest[:LIMIT]}
    return sorted(
        combined.values(), key=lambda row: (row["started_at"], row["attempt_id"])
    ), limited
