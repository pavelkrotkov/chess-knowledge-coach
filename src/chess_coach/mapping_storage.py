"""Persist evidence rows and validate their source-fact references."""

import sqlite3
from typing import cast

from .db import Database
from .fact_fingerprint import canonical


def validate_sources(db: Database, position_id: int, items: list[dict]) -> None:
    for item in items:
        for fact_id in item["fact_ids"]:
            fact = db.connection.execute(
                """SELECT f.position_id, f.run_id, r.status FROM detector_facts f
                LEFT JOIN detector_runs r ON r.id = f.run_id WHERE f.id = ?""",
                (fact_id,),
            ).fetchone()
            if fact is None or fact["position_id"] != position_id:
                raise ValueError("source fact does not belong to mapping position")
            if fact["run_id"] is not None and fact["status"] != "active":
                raise ValueError("source fact is superseded")


def insert_mapping(db: Database, run: dict, item: dict) -> int:
    provenance = "linked"
    for fact_id in item["fact_ids"]:
        source = db.connection.execute(
            "SELECT run_id FROM detector_facts WHERE id = ?", (fact_id,)
        ).fetchone()
        if source["run_id"] is None:
            provenance = "unknown"
    cursor = db.connection.execute(
        """INSERT INTO evidence_mappings
        (position_id, skill, operation, outcome, confidence, source_facts_json,
         mapper_version, context_json, subject, observation_at, mapping_run_id, source_provenance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run["position_id"],
            item["skill"],
            run["operation"],
            item["outcome"],
            item["confidence"],
            canonical(item["fact_ids"]),
            run["mapper_version"],
            canonical(item["context"]),
            run["subject"],
            item["observation_at"],
            run["id"],
            provenance,
        ),
    )
    evidence_id = cast(int, cursor.lastrowid)
    try:
        db.connection.executemany(
            """INSERT INTO evidence_fact_links(evidence_id, fact_id, subject, skill, operation, active)
            VALUES (?, ?, ?, ?, ?, 1)""",
            [
                (evidence_id, fact_id, run["subject"], item["skill"], run["operation"])
                for fact_id in item["fact_ids"]
            ],
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("effective fact already mapped for subject, skill and operation") from exc
    db.connection.execute(
        "UPDATE mastery_states SET is_stale = 1 WHERE subject = ? AND skill = ? AND operation = ?",
        (run["subject"], item["skill"], run["operation"]),
    )
    return evidence_id
