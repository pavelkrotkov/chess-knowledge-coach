"""Complete only enrolled exact canonical immediate-promotion results."""

import sqlite3
from contextlib import suppress

from .learner_identity import normalize_identity
from .unified_training_canonical_promotion import is_forced_source, is_source


def finish_objective(db, request, result):
    if db.compat32 or result.get("status") not in {"correct", "incorrect"}:
        return
    row = db.connection.execute(
        "SELECT * FROM unified_sessions WHERE attempt_id=?", (request["attempt_id"],)
    ).fetchone()
    if (
        row is None
        or normalize_identity(row["subject"]) != request["subject"]
        or not (is_source(row) or is_forced_source(row))
    ):
        return
    if not db.connection.execute(
        "SELECT 1 FROM unified_training_enrollments WHERE attempt_id=?", (row["attempt_id"],)
    ).fetchone():
        return
    from .unified_training_complete import complete

    with suppress(ValueError, sqlite3.Error, RuntimeError, OverflowError):
        complete(db, row["attempt_id"], row["subject"], event_id=request["event_id"])
