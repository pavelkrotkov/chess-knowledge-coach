"""Invalidate mastery only when a review changes effective eligibility."""

from sqlite3 import Row

from .db import Database


def invalidate_changed_eligibility(db: Database, row: Row, decision: str) -> None:
    if (row["human_validated"] == 1) == (decision == "accept"):
        return
    if row["mapping_run_id"] is not None and row["run_status"] != "active":
        return
    db.connection.execute(
        "UPDATE mastery_states SET is_stale = 1 WHERE subject = ? AND skill = ? AND operation = ?",
        (row["subject"], row["skill"], row["operation"]),
    )
