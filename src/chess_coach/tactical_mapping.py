"""Map tactical facts to a scoped, versioned learner interpretation."""

from __future__ import annotations

from typing import Any

from .db import Database
from .mapping_runs import record_mapping_run_in_transaction
from .tactical_report import MAPPER_VERSION, assess_fact

PRODUCER = "mate-in-one-mapper"
SCOPE = "mate-in-one"


def map_decision(
    db: Database,
    decision: dict[str, Any],
    detector_run: dict[str, Any],
    fact: dict[str, Any] | None,
    ontology_version: str,
) -> dict[str, object]:
    assessment = assess_fact(db, decision["position_id"], fact) if fact is not None else None
    if detector_run["status"] != "active":
        return {
            **(assessment or {}),
            "ontology_version": ontology_version,
            "mapping_status": "superseded_detector",
            "mapping_run_id": None,
            "evidence_ids": [],
            "human_validated": False,
        }
    context = _mapping_context(decision, detector_run, fact, ontology_version, assessment)
    items = (
        [] if assessment is None else [_mapping_item(decision, detector_run, context, assessment)]
    )
    run = record_mapping_run_in_transaction(
        db,
        position_id=decision["position_id"],
        producer=PRODUCER,
        mapper_version=MAPPER_VERSION,
        subject=decision["subject"],
        operation="execute",
        scope_key=SCOPE,
        input_data={
            "context": context,
            "assessment": assessment,
            "observation_at": decision["observation_at"],
        },
        mappings=items,
    )
    if assessment is None:
        return {
            "mapping_status": run["status"],
            "mapping_run_id": run["run_id"],
            "evidence_ids": [],
        }
    return {
        **assessment,
        "ontology_version": ontology_version,
        "mapping_status": run["status"],
        "mapping_run_id": run["run_id"],
        "evidence_ids": run["evidence_ids"],
        "human_validated": _reviewed(db, run["evidence_ids"][0]),
    }


def _mapping_context(
    decision: dict[str, Any],
    detector_run: dict[str, Any],
    fact: dict[str, Any] | None,
    ontology_version: str,
    assessment: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "game_id": decision["game_id"],
        "ply": decision["ply"],
        "mover": decision["mover"],
        "pre_move_fen": decision["pre_move_fen"],
        "played_move": decision["played_move"],
        "detector_run_id": detector_run["run_id"],
        "fact_ids": detector_run["fact_ids"],
        "ontology_version": ontology_version,
        "mating_moves": fact["mating_moves"] if fact is not None else [],
        "engine_conflicts": assessment["engine_conflicts"] if assessment is not None else [],
    }


def _mapping_item(
    decision: dict[str, Any],
    detector_run: dict[str, Any],
    context: dict[str, Any],
    assessment: dict[str, Any],
) -> dict[str, Any]:
    return {
        "skill": "mate_in_one",
        "outcome": assessment["outcome"],
        "confidence": assessment["confidence"],
        "fact_ids": detector_run["fact_ids"],
        "context": {**context, "confidence_rationale": assessment["confidence_rationale"]},
        "observation_at": decision["observation_at"],
    }


def _reviewed(db: Database, evidence_id: int) -> bool:
    row = db.connection.execute(
        "SELECT human_validated FROM evidence_mappings WHERE id = ?", (evidence_id,)
    ).fetchone()
    return bool(row["human_validated"])
