"""Persist learner decision facts and preview narrow tactical opportunities."""

from __future__ import annotations

from typing import Any

from .db import Database
from .learner_context import decision_contexts
from .tactical_ontology import seed_tactical_ontology_in_transaction
from .tactical_pipeline_replay import fact_run, mapping_run
from .tactical_rules import mate_in_one_fact

PRODUCER = "mate-in-one"
DETECTOR_VERSION = "1.0.0"


def record_game_opportunities(
    db: Database,
    game_id: int,
    *,
    learner: str | None,
    ontology_version: str = "tactical-mate-v1",
    pipeline_generation: int | None = None,
    require_observation: bool = False,
    detector_version: str = DETECTOR_VERSION,
) -> list[dict[str, object]]:
    """Persist learner decision facts and scoped, unreviewed evidence."""
    if db.connection.in_transaction:
        raise RuntimeError("cannot record tactical facts during an existing transaction")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        result = []
        for context in decision_contexts(db, game_id, learner=learner):
            if context["subject"] is not None and (
                not require_observation or context["observation_at"] is not None
            ):
                seed_tactical_ontology_in_transaction(db, version=ontology_version)
                candidate = _record_decision(
                    db, context, ontology_version, pipeline_generation, detector_version
                )
                if candidate is not None:
                    result.append(candidate)
        db.connection.commit()
        return result
    except BaseException:
        db.connection.rollback()
        raise


def _record_decision(
    db: Database,
    context: dict[str, Any],
    ontology_version: str,
    pipeline_generation: int | None,
    detector_version: str,
) -> dict[str, object] | None:
    fen, played = context["pre_move_fen"], context["played_move"]
    fact = mate_in_one_fact(fen, played)
    facts = [] if fact is None else [{"fact_type": "mate_in_one", "payload": fact}]
    run = fact_run(db, context, PRODUCER, detector_version, facts, pipeline_generation)
    mapping = mapping_run(db, context, run, fact, ontology_version, pipeline_generation)
    if fact is None:
        return None
    return {
        "game_id": context["game_id"],
        "position_id": context["position_id"],
        "ply": context["ply"],
        "mover": context["mover"],
        "pre_move_fen": fen,
        "played_move": played,
        "mating_moves": fact["mating_moves"],
        "detector_version": detector_version,
        "detector_run_id": run["run_id"],
        "detector_status": run["status"],
        "source_fact_ids": run["fact_ids"],
        **mapping,
    }
