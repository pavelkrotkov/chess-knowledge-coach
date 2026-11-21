"""Publish learning only for enrolled, qualified fork results."""

import sqlite3
from contextlib import suppress


def finish_objective(db, request, result):
    from .objective_contract import OWNED_HISTORY
    from .objective_fork_contract import MISS_OBJECTIVE
    from .unified_capture_worker import finish_objective as finish_capture

    finish_capture(db, request, result)
    if db.compat32:
        return
    if (result["status"], request["objective_version"], request["history_mode"]) not in {
        ("correct", MISS_OBJECTIVE, OWNED_HISTORY),
        ("incorrect", MISS_OBJECTIVE, OWNED_HISTORY),
    }:
        return
    if (
        db.connection.execute(
            "SELECT 1 FROM unified_training_enrollments WHERE attempt_id=?",
            (request["attempt_id"],),
        ).fetchone()
        is None
    ):
        return
    from .unified_fork_completion import complete

    with suppress(ValueError, sqlite3.Error, RuntimeError, OverflowError):
        complete(db, request["attempt_id"], request["subject"], event_id=request["event_id"])
