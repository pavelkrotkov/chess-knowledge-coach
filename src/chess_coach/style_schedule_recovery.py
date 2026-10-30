"""Record an interrupted purpose claim after a scheduling budget stops it."""

from .deep_execution_lock import deep_lock
from .purpose_claim import claim


def abandon(db, request_id, learner):
    if request_id is None:
        return True
    try:
        with deep_lock(db.path):
            row = db.connection.execute(
                "SELECT status FROM purpose_analysis_requests WHERE id=?", (request_id,)
            ).fetchone()
            if row is not None and row["status"] == "running":
                claim(db, request_id, learner, retry=False)
        return True
    except RuntimeError:
        return False
