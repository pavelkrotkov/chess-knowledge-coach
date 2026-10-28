"""Persist learner decision facts and preview narrow tactical opportunities."""

from __future__ import annotations

from typing import Any

from .db import Database
from .fact_runs import record_fact_run_in_transaction
from .learner_context import decision_contexts
from .tactical_report import assess_fact
from .tactical_rules import mate_in_one_fact

PRODUCER = "mate-in-one"
DETECTOR_VERSION = "1.0.0"


def record_game_opportunities(
    db: Database, game_id: int, *, learner: str | None
) -> list[dict[str, object]]:
    """Persist deterministic facts for attributed decisions; return reviewable previews."""
    if db.connection.in_transaction:
        raise RuntimeError("cannot record tactical facts during an existing transaction")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        result = []
        for context in decision_contexts(db, game_id, learner=learner):
            if context["subject"] is not None:
                candidate = _record_decision(db, context)
                if candidate is not None:
                    result.append(candidate)
        db.connection.commit()
        return result
    except BaseException:
        db.connection.rollback()
        raise


def _record_decision(db: Database, context: dict[str, Any]) -> dict[str, object] | None:
    fen, played = context["pre_move_fen"], context["played_move"]
    fact = mate_in_one_fact(fen, played)
    facts = [] if fact is None else [{"fact_type": "mate_in_one", "payload": fact}]
    run = record_fact_run_in_transaction(
        db,
        position_id=context["position_id"],
        producer=PRODUCER,
        detector_version=DETECTOR_VERSION,
        input_data={"pre_move_fen": fen, "played_move": played},
        facts=facts,
    )
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
        "detector_version": DETECTOR_VERSION,
        "detector_run_id": run["run_id"],
        "detector_status": run["status"],
        "source_fact_ids": run["fact_ids"],
        **assess_fact(db, context["position_id"], fact),
    }
