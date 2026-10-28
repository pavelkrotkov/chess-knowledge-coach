"""Append a validated mapping run and replace only its owned scope."""

from datetime import UTC, datetime
from typing import cast

from .db import Database
from .fact_fingerprint import digest
from .mapping_invalidation import supersede_mapping
from .mapping_storage import insert_mapping


def append_run(
    db: Database, scope: tuple, version: str, input_json: str, output_hash: str, items: list[dict]
) -> dict:
    prior = db.connection.execute(
        """SELECT * FROM mapping_runs WHERE producer = ? AND position_id = ?
        AND subject = ? AND operation = ? AND scope_key = ? ORDER BY id DESC LIMIT 1""",
        scope,
    ).fetchone()
    if prior is not None and prior["status"] == "active":
        supersede_mapping(db, prior["id"])
    cursor = db.connection.execute(
        """INSERT INTO mapping_runs(producer, position_id, subject, operation, scope_key,
        mapper_version, input_json, input_hash, output_hash, created_at, status, supersedes_run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
        (
            *scope,
            version,
            input_json,
            digest(input_json),
            output_hash,
            datetime.now(UTC).isoformat(),
            prior["id"] if prior else None,
        ),
    )
    run_id = cast(int, cursor.lastrowid)
    run = {
        "id": run_id,
        "position_id": scope[1],
        "subject": scope[2],
        "operation": scope[3],
        "mapper_version": version,
    }
    ids = [insert_mapping(db, run, item) for item in items]
    return {"run_id": run_id, "evidence_ids": ids, "status": "active", "replayed": False}
