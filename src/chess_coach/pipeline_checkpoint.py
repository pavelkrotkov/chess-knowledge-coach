"""Durable stage checkpoints; callers control commit and rollback."""

import sqlite3
from datetime import UTC, datetime

from .pipeline_generation_state import superseded
from .pipeline_output import output_is_current


def current(connection: sqlite3.Connection, game_id: int, stage: str, fingerprint: str):
    row = connection.execute(
        'SELECT * FROM pipeline_stages WHERE game_id=? AND stage=? AND input_hash=? AND status IN ("complete","skipped")',
        (game_id, stage, fingerprint),
    ).fetchone()
    return row if row is not None and output_is_current(connection, row) else None


def checkpoint(
    connection: sqlite3.Connection,
    game_id: int,
    stage: str,
    fingerprint: str,
    status: str,
    detail: str,
    output_id: int | None = None,
    output_hash: str | None = None,
) -> None:
    connection.execute(
        """INSERT INTO pipeline_stages
        (game_id,stage,input_hash,status,detail,output_id,output_hash,updated_at) VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(game_id,stage) DO UPDATE SET input_hash=excluded.input_hash,
        status=excluded.status,detail=excluded.detail,output_id=excluded.output_id,output_hash=excluded.output_hash,
        updated_at=excluded.updated_at""",
        (
            game_id,
            stage,
            fingerprint,
            status,
            detail,
            output_id,
            output_hash,
            datetime.now(UTC).isoformat(),
        ),
    )


def prepare_generation(
    connection: sqlite3.Connection, game_id: int, stage: str, fingerprint: str
) -> int:
    row = connection.execute(
        "SELECT input_hash,generation,status FROM pipeline_stages WHERE game_id=? AND stage=?",
        (game_id, stage),
    ).fetchone()
    generation = (
        1
        if row is None
        else row["generation"]
        + int(
            row["input_hash"] != fingerprint
            or row["status"] == "complete"
            or superseded(connection, game_id, stage, row["generation"])
        )
    )
    connection.execute(
        """INSERT INTO pipeline_stages
        (game_id,stage,input_hash,status,detail,generation,updated_at)
        VALUES (?,?,?,"pending","processing",?,?) ON CONFLICT(game_id,stage) DO UPDATE SET
        input_hash=excluded.input_hash,status="pending",detail="processing",output_id=NULL,
        generation=excluded.generation,updated_at=excluded.updated_at""",
        (game_id, stage, fingerprint, generation, datetime.now(UTC).isoformat()),
    )
    return generation
