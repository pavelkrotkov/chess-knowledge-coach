"""Persist one detector output and its evidence in the same transaction."""

from .db import Database
from .fact_inputs import prepare_fact
from .fact_runs import record_fact_run_in_transaction
from .mapping_runs import record_mapping_run_in_transaction


def persist_run(
    db: Database,
    position_id: int,
    detector_version: str,
    mapper_version: str,
    operation: str,
    facts: list[dict],
    outcomes: list[str],
) -> None:
    prepared = [{"fact_type": fact["motif"], "payload": fact} for fact in facts]
    run = record_fact_run_in_transaction(
        db,
        position_id=position_id,
        producer="motif",
        detector_version=detector_version,
        input_data={},
        facts=prepared,
    )
    if run["status"] != "active":
        return
    keys = {
        row["fact_key"]: row["id"]
        for row in db.connection.execute(
            "SELECT id, fact_key FROM detector_facts WHERE run_id = ?", (run["run_id"],)
        )
    }
    mappings = [
        {
            "skill": fact["motif"],
            "outcome": value,
            "confidence": 1.0,
            "fact_ids": [keys[prepare_fact(item)[0]]],
            "context": {},
            "observation_at": None,
        }
        for fact, item, value in zip(facts, prepared, outcomes, strict=True)
    ]
    record_mapping_run_in_transaction(
        db,
        position_id=position_id,
        producer="motif",
        mapper_version=mapper_version,
        subject="unassigned",
        operation=operation,
        scope_key="motifs",
        input_data={"detector_run_id": run["run_id"], "outcomes": outcomes},
        mappings=mappings,
    )
