"""Apply one validated detector run within a caller-owned transaction."""

from __future__ import annotations

from datetime import UTC, datetime

from .db import Database
from .fact_fingerprint import canonical, digest
from .fact_storage import insert_fact, insert_run, previous_run, replay_result


def persist_run(
    db: Database,
    position_id: int,
    producer: str,
    version: str,
    input_data: dict,
    items: list[tuple[str, str, str]],
    output_hash: str,
) -> dict:
    position = db.connection.execute(
        "SELECT fen FROM positions WHERE id = ?", (position_id,)
    ).fetchone()
    if position is None:
        raise ValueError(f"unknown position id: {position_id}")
    input_json = canonical({"position_fen": position["fen"], "detector_input": input_data})
    input_hash = digest(input_json)
    existing = db.connection.execute(
        """SELECT * FROM detector_runs
        WHERE producer = ? AND position_id = ? AND detector_version = ? AND input_hash = ?""",
        (producer, position_id, version, input_hash),
    ).fetchone()
    if existing is not None:
        if existing["input_json"] != input_json:
            raise ValueError("detector input identity conflict")
        return replay_result(db.connection, existing, output_hash, items)
    prior = previous_run(db.connection, producer, position_id)
    prior_id = prior["id"] if prior is not None else None
    if prior_id is not None:
        db.connection.execute(
            "UPDATE detector_runs SET status = 'superseded' WHERE id = ?", (prior_id,)
        )
    produced_at = datetime.now(UTC).isoformat()
    run_id = insert_run(
        db.connection,
        producer=producer,
        position_id=position_id,
        version=version,
        input_json=input_json,
        input_hash=input_hash,
        output_hash=output_hash,
        produced_at=produced_at,
        previous=prior_id,
    )
    ids = [
        insert_fact(
            db.connection,
            position_id=position_id,
            version=version,
            run_id=run_id,
            key=key,
            fact_type=fact_type,
            payload=payload,
            produced_at=produced_at,
        )
        for key, fact_type, payload in items
    ]
    return {"run_id": run_id, "fact_ids": ids, "status": "active", "replayed": False}
