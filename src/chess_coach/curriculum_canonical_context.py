"""Bounded positive promotion-practice context without mastery inference."""

from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity
from .plan_promotion_catalog import VERSION, collection
from .plan_promotion_history import completed

LIMIT = 25


def _inventory(db, limit):
    # All statuses count as activity; the shared SQLite deadline bounds the scan.
    return db.connection.execute(
        """SELECT * FROM unified_sessions INDEXED BY idx_unified_sessions_subject
        WHERE source_type='public' AND source_version=?
        ORDER BY started_at DESC,attempt_id DESC LIMIT ?""",
        (VERSION, limit + 1),
    ).fetchall()


def context(db, subject, limit, check):
    check()
    tasks = collection(db)
    cap = min(limit, LIMIT)
    rows = _inventory(db, cap)
    current = []
    for row in rows[:cap]:
        check()
        if normalize_identity(row["subject"]) == subject:
            current.append(row)
    done = completed(db, subject, [task["task_id"] for task in tasks], check=check, rows=current)
    if done:
        scope = digest(canonical(["continuation", sorted(done)]))
        return {"state": "continuation", "scope": scope, "done": done, "tasks": tasks}
    first = not current and len(rows) <= cap
    if first:
        scope = digest(canonical(["first-recorded", VERSION]))
        return {"state": "first_recorded", "scope": scope, "done": done, "tasks": tasks}
    status = "incomplete" if len(rows) > cap else "unavailable"
    return {"state": status, "scope": None, "done": done, "tasks": tasks}
