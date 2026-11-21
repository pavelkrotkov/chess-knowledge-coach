"""Publish learning only for enrolled, qualified capture results."""

import sqlite3
from contextlib import suppress


def finish_objective(db, request, result):
    from .objective_capture_contract import TARGET_OBJECTIVE
    from .objective_contract import OWNED_HISTORY

    if db.compat32:
        return
    if (result["status"], request["objective_version"], request["history_mode"]) not in {
        ("correct", TARGET_OBJECTIVE, OWNED_HISTORY),
        ("incorrect", TARGET_OBJECTIVE, OWNED_HISTORY),
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
    from .unified_capture_completion import complete

    with suppress(ValueError, sqlite3.Error, RuntimeError, OverflowError):
        complete(db, request["attempt_id"], request["subject"], event_id=request["event_id"])
