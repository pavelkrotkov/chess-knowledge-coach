"""Read linked source facts and their detector provenance."""

from __future__ import annotations

from .db import Database
from .evidence_review_json import decode


def facts_for_evidence(db: Database, evidence_id: int) -> list[dict]:
    rows = db.connection.execute(
        """SELECT f.id, f.fact_type, f.payload_json, f.detector_version, f.produced_at,
                  f.run_id, r.producer, r.detector_version AS run_detector_version, r.status AS detector_status
        FROM evidence_fact_links l
        JOIN detector_facts f ON f.id = l.fact_id
        LEFT JOIN detector_runs r ON r.id = f.run_id
        WHERE l.evidence_id = ? ORDER BY f.id""",
        (evidence_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "fact_type": row["fact_type"],
            "payload": decode(row["payload_json"]),
            "detector_version": row["detector_version"],
            "produced_at": row["produced_at"],
            "detector_run_id": row["run_id"],
            "run_detector_version": row["run_detector_version"],
            "producer": row["producer"],
            "detector_status": row["detector_status"],
        }
        for row in rows
    ]
