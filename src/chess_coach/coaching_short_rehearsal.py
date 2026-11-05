"""Recognize fully played, unassisted prepared short-mate rehearsals."""

from .coaching_short_rehearsal_check import completed as is_completed


def rehearsed_sources(db, subject, keys, boards=frozenset()):
    if not keys and not boards:
        return {}
    rows = db.connection.execute(
        """SELECT * FROM unified_sessions INDEXED BY idx_unified_sessions_subject
        WHERE subject=? ORDER BY started_at DESC,attempt_id LIMIT 100""",
        (subject,),
    ).fetchall()
    completed = {}
    for row in rows:
        key = row["source_key"]
        board = " ".join(row["prompt_fen"].split()[:4])
        if (key in keys or board in boards) and key not in completed and is_completed(db, row):
            completed[key] = board
    return completed
