"""Read bounded oldest and newest sessions through the subject-time index."""

LIMIT = 100


def _end(db, subject, order):
    return db.connection.execute(
        f"""SELECT * FROM unified_sessions INDEXED BY idx_unified_sessions_subject
        WHERE subject=? ORDER BY started_at {order},attempt_id {"DESC" if order == "ASC" else "ASC"}
        LIMIT ?""",
        (subject, LIMIT + 1),
    ).fetchall()


def rows(db, subject):
    oldest = _end(db, subject, "ASC")
    newest = _end(db, subject, "DESC")
    all_rows = {row["attempt_id"]: row for row in oldest + newest}
    limited = len(all_rows) > 2 * LIMIT
    if limited:
        all_rows = {row["attempt_id"]: row for row in oldest[:LIMIT] + newest[:LIMIT]}
    return sorted(
        all_rows.values(), key=lambda row: (row["started_at"], row["attempt_id"])
    ), limited
