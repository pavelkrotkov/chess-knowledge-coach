"""Select bounded subject-owned fork attempts in stable reverse order."""

from .objective_fork_contract import GOAL

PAGE = 20


def rows(db, subject, before):
    condition = ""
    params = [subject, "corpus", GOAL]
    if before is not None:
        condition = " AND (started_at<? OR (started_at=? AND attempt_id<?))"
        params.extend((before[0], before[0], before[1]))
    params.append(PAGE + 1)
    return db.connection.execute(
        """SELECT * FROM unified_sessions INDEXED BY idx_unified_sessions_subject
        WHERE subject=? AND source_type=? AND objective=?"""
        + condition
        + " ORDER BY started_at DESC,attempt_id DESC LIMIT ?",
        params,
    ).fetchall()
