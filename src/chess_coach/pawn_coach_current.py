"""Recheck pawn evidence against its active link and freshly proved source."""

import json

from .pawn_coach_contract import MAPPER
from .pawn_coach_current_mapping import valid_mapping
from .pawn_coach_current_record import valid_record
from .pawn_coach_mapping import mapping_context, operation
from .pawn_coach_source import prepare


def current_pawn(db, evidence):
    if evidence["mapping_producer"] != MAPPER:
        return None, None
    if not valid_record(db, evidence):
        return None, "stale"
    fact = evidence["facts"][0]
    try:
        prepared = prepare(db, evidence["position_id"], evidence["subject"])
        stored = db.connection.execute(
            "SELECT input_json FROM detector_runs WHERE id=?", (fact["detector_run_id"],)
        ).fetchone()
        inputs = json.loads(stored["input_json"])["detector_input"]
        inputs = {k: v for k, v in inputs.items() if k != "reactivation"}
        valid = _matches(evidence, fact, prepared, inputs) and valid_mapping(
            db, evidence, fact, prepared
        )
    except (ValueError, TypeError, KeyError, AttributeError):
        return None, "stale"
    return (prepared, "current") if valid else (None, "stale")


def _matches(evidence, fact, prepared, inputs):
    return (
        inputs == prepared["inputs"]
        and fact["payload"] == prepared["fact"]
        and evidence["context"] == mapping_context(prepared)
        and evidence["operation"] == operation(prepared["fact"])
        and evidence["outcome"] == prepared["fact"]["outcome"]
    )
