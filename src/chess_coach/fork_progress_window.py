"""Bound the recent fork-session window without splitting a tied timestamp."""

from .objective_fork_contract import GOAL

LIMIT = 200


def rows(db, subject, corpus):
    rows = db.connection.execute(
        """SELECT * FROM unified_sessions INDEXED BY idx_unified_sessions_subject
        WHERE subject=? AND source_type=? AND source_version=? AND objective=?
        ORDER BY started_at DESC,attempt_id LIMIT ?""",
        (subject, "corpus", corpus, GOAL, LIMIT + 1),
    ).fetchall()
    window_limited = len(rows) > LIMIT
    tied = window_limited and rows[LIMIT - 1]["started_at"] == rows[LIMIT]["started_at"]
    selected = sorted(rows[:LIMIT], key=lambda row: (row["started_at"], row["attempt_id"]))
    return selected, window_limited, tied
