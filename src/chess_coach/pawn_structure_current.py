"""Revalidate a lesson against its active source and full current input."""

import json

from .material_opportunity_links import valid_link
from .material_replay import source_inputs
from .pawn_structure_mapping import MAPPER
from .pawn_structure_source import prepare_lesson


def _active(db, evidence, facts):
    return (
        len(facts) == 1
        and evidence["lifecycle_status"] == "active"
        and facts[0]["detector_status"] == "active"
        and valid_link(db, evidence, facts[0])
    )


def currentness(db, evidence, *, _history=None):
    if evidence["mapping_producer"] != MAPPER:
        return None
    facts = evidence["facts"]
    if not _active(db, evidence, facts):
        return "stale"
    try:
        prepared, lesson = prepare_lesson(
            db, evidence["position_id"], evidence["subject"], _history=_history
        )
        row = db.connection.execute(
            "SELECT input_json FROM detector_runs WHERE id=?", (facts[0]["detector_run_id"],)
        ).fetchone()
        saved = json.loads(row[0])["detector_input"]
        saved.pop("reactivation", None)
        if saved != source_inputs(prepared) or lesson != facts[0]["payload"]:
            return "stale"
        if evidence["context"]["lesson"] != lesson:
            return "stale"
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        return "stale"
    return "current"
