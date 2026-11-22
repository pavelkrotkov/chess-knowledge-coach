"""Bounded positive promotion-practice context without mastery inference."""

from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity
from .plan_promotion_catalog import VERSION, collection
from .plan_promotion_history import completed

LIMIT = 25


def _sessions(db, subject, limit):
    return db.connection.execute(
        """SELECT * FROM unified_sessions INDEXED BY idx_unified_sessions_subject
        WHERE subject=? AND source_type='public' AND source_version=?
        ORDER BY started_at DESC,attempt_id DESC LIMIT ?""",
        (subject, VERSION, limit + 1),
    ).fetchall()


def _first_recorded(db, subject, limit, rows, check):
    if len(rows) > limit:
        return None
    # Look across every status, including pending, missed and assisted attempts.
    history = db.connection.execute(
        """SELECT subject,source_type,source_version FROM unified_sessions
        INDEXED BY idx_unified_sessions_subject
        WHERE source_type='public' AND source_version=? LIMIT ?""",
        (VERSION, limit + 1),
    ).fetchall()
    for row in history:
        check()
        if (
            normalize_identity(row["subject"]) == subject
            and row["source_type"] == "public"
            and row["source_version"] == VERSION
        ):
            return False
    return None if len(history) > limit else True


def context(db, subject, limit, check):
    check()
    tasks = collection(db)
    cap = min(limit, LIMIT)
    rows = _sessions(db, subject, cap)
    current = [
        row
        for row in rows[:cap]
        if row["source_type"] == "public" and row["source_version"] == VERSION
    ]
    done = completed(db, subject, [task["task_id"] for task in tasks], check=check, rows=current)
    if done:
        scope = digest(canonical(["continuation", sorted(done)]))
        return {"state": "continuation", "scope": scope, "done": done, "tasks": tasks}
    first = _first_recorded(db, subject, cap, rows, check)
    if first:
        scope = digest(canonical(["first-recorded", VERSION]))
        return {"state": "first_recorded", "scope": scope, "done": done, "tasks": tasks}
    status = "incomplete" if first is None else "unavailable"
    return {"state": status, "scope": None, "done": done, "tasks": tasks}
