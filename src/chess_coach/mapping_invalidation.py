"""Invalidate derived current views while preserving all historical records."""

from .db import Database


def supersede_mapping(db: Database, run_id: int) -> None:
    db.connection.execute(
        """UPDATE mastery_states SET is_stale = 1
        WHERE (subject, skill, operation) IN
        (SELECT subject, skill, operation FROM evidence_mappings WHERE mapping_run_id = ?)""",
        (run_id,),
    )
    db.connection.execute(
        """UPDATE evidence_fact_links SET active = 0 WHERE evidence_id IN
        (SELECT id FROM evidence_mappings WHERE mapping_run_id = ?)""",
        (run_id,),
    )
    db.connection.execute("UPDATE mapping_runs SET status = 'superseded' WHERE id = ?", (run_id,))


def supersede_detector_mappings(db: Database, detector_run_id: int) -> None:
    rows = db.connection.execute(
        """SELECT DISTINCT m.id FROM mapping_runs m
        JOIN evidence_mappings e ON e.mapping_run_id = m.id
        JOIN evidence_fact_links l ON l.evidence_id = e.id
        JOIN detector_facts f ON f.id = l.fact_id
        WHERE f.run_id = ? AND m.status = 'active'""",
        (detector_run_id,),
    ).fetchall()
    for row in rows:
        supersede_mapping(db, row["id"])
