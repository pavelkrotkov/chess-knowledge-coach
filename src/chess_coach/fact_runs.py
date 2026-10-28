"""Append-only detector output with explicit producer and position lineage."""

from __future__ import annotations

from typing import Any

from .db import Database
from .fact_inputs import fact_batch
from .fact_run_apply import persist_run


def record_fact_run(
    db: Database,
    *,
    position_id: int,
    producer: str,
    detector_version: str,
    input_data: dict[str, Any],
    facts: list[dict[str, Any]],
) -> dict:
    if db.connection.in_transaction:
        raise RuntimeError("cannot record detector output during an existing transaction")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        result = record_fact_run_in_transaction(
            db,
            position_id=position_id,
            producer=producer,
            detector_version=detector_version,
            input_data=input_data,
            facts=facts,
        )
        db.connection.commit()
        return result
    except BaseException:
        db.connection.rollback()
        raise


def record_fact_run_in_transaction(
    db: Database,
    *,
    position_id: int,
    producer: str,
    detector_version: str,
    input_data: dict[str, Any],
    facts: list[dict[str, Any]],
) -> dict:
    """Persist within the caller transaction; never commit or roll it back."""
    if not db.connection.in_transaction:
        raise RuntimeError("detector output requires a transaction")
    if not isinstance(producer, str) or not producer.strip():
        raise ValueError("producer must be nonempty")
    if not isinstance(detector_version, str) or not detector_version.strip():
        raise ValueError("detector version must be nonempty")
    if not isinstance(input_data, dict):
        raise ValueError("detector input must be an object")
    items, output_hash = fact_batch(facts)
    return persist_run(db, position_id, producer, detector_version, input_data, items, output_hash)
