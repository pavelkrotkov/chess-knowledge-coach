"""Link descriptive lessons to reviewable, always ambiguous observations."""

import json

from .king_safety_lesson import VERSION
from .mapping_runs import record_mapping_run_in_transaction

MAPPER = "king-safety-lesson-mapper"


def mapping(db, prepared, inputs, run, fact):
    context = prepared["context"]
    details = {
        "game_id": prepared["game_id"],
        "ply": context["ply"],
        "pre_move_fen": context["pre_move_fen"],
        "played_move": context["played_move"],
        "lesson": fact,
        "provenance": prepared["provenance"],
    }
    items = (
        []
        if fact is None
        else [
            {
                "skill": "king_safety",
                "outcome": "ambiguous",
                "confidence": 0.5,
                "fact_ids": run["fact_ids"],
                "context": details,
                "observation_at": context["observation_at"],
            }
        ]
    )
    data = {"source": inputs, "fact_run": run["run_id"], "context": details}
    active = db.connection.execute(
        "SELECT input_json FROM mapping_runs WHERE position_id=? AND producer=? AND subject=? AND operation=? AND scope_key=? AND status='active'",
        (prepared["position_id"], MAPPER, context["subject"], "evaluate", "king-safety-lesson"),
    ).fetchone()
    if active:
        prior = json.loads(active[0])
        if {key: value for key, value in prior.items() if key != "reactivation"} == data:
            data = prior
    result = _record(db, prepared, data, items)
    if result["status"] != "active":
        latest = db.connection.execute(
            "SELECT MAX(id) FROM mapping_runs WHERE producer=? AND position_id=?",
            (MAPPER, prepared["position_id"]),
        ).fetchone()[0]
        result = _record(db, prepared, {**data, "reactivation": latest}, items)
    return result


def _record(db, prepared, data, items):
    return record_mapping_run_in_transaction(
        db,
        position_id=prepared["position_id"],
        producer=MAPPER,
        mapper_version=VERSION,
        subject=prepared["context"]["subject"],
        operation="evaluate",
        scope_key="king-safety-lesson",
        input_data=data,
        mappings=items,
    )
