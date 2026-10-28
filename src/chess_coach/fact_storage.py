"""SQLite persistence for immutable detector runs and fact identities."""

from __future__ import annotations

import sqlite3


def previous_run(
    connection: sqlite3.Connection, producer: str, position_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM detector_runs WHERE producer = ? AND position_id = ? AND status = 'active'",
        (producer, position_id),
    ).fetchone()


def insert_run(
    connection: sqlite3.Connection,
    *,
    producer: str,
    position_id: int,
    version: str,
    input_json: str,
    input_hash: str,
    output_hash: str,
    produced_at: str,
    previous: int | None,
) -> int:
    cursor = connection.execute(
        """INSERT INTO detector_runs
        (producer, position_id, detector_version, input_json, input_hash, output_hash,
         produced_at, status, supersedes_run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
        (
            producer,
            position_id,
            version,
            input_json,
            input_hash,
            output_hash,
            produced_at,
            previous,
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("SQLite did not return a detector run ID")
    return cursor.lastrowid


def insert_fact(
    connection: sqlite3.Connection,
    *,
    position_id: int,
    version: str,
    run_id: int,
    key: str,
    fact_type: str,
    payload: str,
    produced_at: str,
) -> int:
    cursor = connection.execute(
        """INSERT INTO detector_facts
        (position_id, detector_version, fact_type, payload_json, run_id, fact_key, produced_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (position_id, version, fact_type, payload, run_id, key, produced_at),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("SQLite did not return a fact ID")
    return cursor.lastrowid


def replay_result(
    connection: sqlite3.Connection,
    run: sqlite3.Row,
    output_hash: str,
    items: list[tuple[str, str, str]],
) -> dict:
    if run["output_hash"] != output_hash:
        raise ValueError("detector output changed for the same input and version")
    rows = connection.execute(
        "SELECT id, fact_key, fact_type, payload_json FROM detector_facts "
        "WHERE run_id = ? ORDER BY fact_key",
        (run["id"],),
    ).fetchall()
    stored = [(row["fact_key"], row["fact_type"], row["payload_json"]) for row in rows]
    if stored != items:
        raise ValueError("stored facts no longer match the detector run")
    return {
        "run_id": run["id"],
        "fact_ids": [row["id"] for row in rows],
        "status": run["status"],
        "replayed": True,
    }
