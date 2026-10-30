"""Claim one request and append terminal attempts under short transactions."""

from .fact_fingerprint import canonical
from .purpose_current import current, owned


def record(db, row, status, detail, result):
    db.connection.execute(
        """INSERT INTO purpose_analysis_attempts
        (request_id,attempt_number,status,detail,result_json) VALUES(?,?,?,?,?)""",
        (row["id"], row["attempt_count"], status, detail, canonical(result)),
    )
    db.connection.execute(
        "UPDATE purpose_analysis_requests SET status=? WHERE id=?", (status, row["id"])
    )


def finish(db, request_id, learner, status, detail, result):
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        row = owned(db, request_id, learner)
        if row["status"] != "running":
            raise ValueError("purpose claim is no longer current")
        try:
            current(db, row, learner)
        except ValueError:
            status, detail = "stale", "source_changed"
        record(db, row, status, detail, result)
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise
    return {"request_id": request_id, "status": status, "detail": detail}
