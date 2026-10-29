"""Claim a single job and append an auditable attempt."""

from .deep_execution_selection import current_selection
from .mapping_transaction import mapping_transaction


def claim_job(db, job, learner):
    with mapping_transaction(db):
        current_selection(db, job["selection_id"], learner)
        row = db.connection.execute(
            "SELECT status FROM deep_analysis_jobs WHERE id=?", (job["id"],)
        ).fetchone()
        if row is None or row["status"] != "pending":
            raise ValueError("deep job is no longer pending")
        number = db.connection.execute(
            "SELECT COALESCE(MAX(attempt_number),0)+1 FROM deep_analysis_attempts WHERE job_id=?",
            (job["id"],),
        ).fetchone()[0]
        cursor = db.connection.execute(
            """INSERT INTO deep_analysis_attempts(job_id,attempt_number,status,detail,comparison)
            VALUES(?,?,'running','processing','unknown')""",
            (job["id"], number),
        )
        db.connection.execute(
            "UPDATE deep_analysis_jobs SET status='running',updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (job["id"],),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("deep attempt could not be stored")
        return cursor.lastrowid
