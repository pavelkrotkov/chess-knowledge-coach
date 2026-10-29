"""Create owned, immutable diagnostic tasks with fresh source checks."""

import json

from .probe_design import design
from .probe_views import show
from .unified_session_state import now


def start(db, subject, attempt_id, lesson_id, evidence_id, kind):
    if not isinstance(attempt_id, str) or not 0 < len(attempt_id) <= 256:
        raise ValueError("invalid attempt")
    if db.connection.in_transaction:
        raise RuntimeError("cannot start during a transaction")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        task, fingerprint, position = design(db, subject, lesson_id, evidence_id, kind)
        row = db.connection.execute(
            "SELECT * FROM diagnostic_probes WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        if row:
            if (
                row["subject"],
                row["lesson_id"],
                row["evidence_id"],
                row["task_json"],
                row["source_hash"],
            ) != (subject, lesson_id, evidence_id, json.dumps(task, sort_keys=True), fingerprint):
                raise ValueError("attempt belongs to another source")
        else:
            db.connection.execute(
                """INSERT INTO diagnostic_probes
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    attempt_id,
                    subject,
                    lesson_id,
                    evidence_id,
                    position,
                    json.dumps(task, sort_keys=True),
                    fingerprint,
                    now(),
                ),
            )
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise
    return show(db, subject, attempt_id)
