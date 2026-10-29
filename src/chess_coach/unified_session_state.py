"""Load subject-owned attempts and expose only non-solution session state."""

from datetime import UTC, datetime


def now():
    return datetime.now(UTC).isoformat()


def session_row(db, attempt_id, subject):
    row = db.connection.execute(
        "SELECT * FROM unified_sessions WHERE attempt_id=? AND subject=?", (attempt_id, subject)
    ).fetchone()
    if row is None:
        raise ValueError("unknown practice attempt")
    return row


def view(row):
    return {
        "attempt_id": row["attempt_id"],
        "source_type": row["source_type"],
        "source_version": row["source_version"],
        "source_key": row["source_key"],
        "fen": row["current_fen"],
        "learner_color": row["learner_color"],
        "objective": row["objective"],
        "status": row["status"],
        "hints_used": row["hints_used"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


def recent(db, subject):
    rows = db.connection.execute(
        """SELECT attempt_id,source_type,source_version,source_key,status
        FROM unified_sessions WHERE subject=? ORDER BY started_at DESC,attempt_id LIMIT 20""",
        (subject,),
    ).fetchall()
    return [dict(row) for row in rows]
