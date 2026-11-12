"""Find bounded current canonical promotion completions per task."""

from .plan_promotion_catalog import VERSION
from .plan_promotion_completion import complete

LIMIT = 25


def _rows(db, subject, key):
    return db.connection.execute(
        """SELECT s.* FROM unified_sessions s WHERE s.subject=? AND s.source_type='public'
        AND s.source_version=? AND s.source_key=? AND s.hints_used=0
        AND s.status IN ('needs_verification','objective_verified')
        AND EXISTS (
          SELECT 1 FROM objective_requests q JOIN objective_results r
          ON r.attempt_id=q.attempt_id AND r.event_id=q.event_id
          WHERE q.attempt_id=s.attempt_id AND json_valid(r.result_json)
          AND json_extract(r.result_json,'$.status')='correct'
          AND json_extract(r.result_json,'$.assistance')='unassisted'
          AND (s.status='objective_verified' OR
               (s.status='needs_verification'
                AND json_extract(r.result_json,'$.reason')='promotion_performed'))
        ) ORDER BY s.started_at DESC,s.attempt_id DESC LIMIT ?""",
        (subject, VERSION, key, LIMIT + 1),
    ).fetchall()


def _verified(db, rows):
    for row in rows[:LIMIT]:
        try:
            if complete(db, row):
                return True
        except (ValueError, TypeError, KeyError, IndexError):
            continue
    if len(rows) > LIMIT:
        raise ValueError("promotion history exceeds the checked bound")
    return False


def completed(db, subject, keys):
    return {key for key in keys if _verified(db, _rows(db, subject, key))}
