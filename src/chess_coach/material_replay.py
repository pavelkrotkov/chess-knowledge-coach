"""Recognize an unchanged active material decision without rerunning verification."""

import json

from .material_contract import PRODUCER
from .material_replay_rows import current_version, mapped_result


def source_inputs(prepared):
    context = prepared["context"]
    return {
        "source_marker": prepared["source_marker"],
        "provenance": prepared["provenance"],
        "pre_move_fen": context["pre_move_fen"],
        "played_move": context["played_move"],
    }


def current_result(db, prepared):
    row = db.connection.execute(
        """SELECT id,input_json,detector_version FROM detector_runs WHERE position_id=? AND producer=?
        AND status=?""",
        (prepared["position_id"], PRODUCER, "active"),
    ).fetchone()
    if row is None:
        return None
    try:
        prior = json.loads(row["input_json"])["detector_input"]
    except (TypeError, ValueError, KeyError):
        return None
    if {key: value for key, value in prior.items() if key != "reactivation"} != source_inputs(
        prepared
    ):
        return None
    facts = db.connection.execute(
        "SELECT id,payload_json FROM detector_facts WHERE run_id=?", (row["id"],)
    ).fetchall()
    if not current_version(row, facts):
        return None
    if not facts:
        return {
            "detector_run_id": row["id"],
            "fact_ids": [],
            "mapping_run_id": None,
            "evidence_ids": [],
            "replayed": True,
            "outcome": "no_opportunity",
        }
    return mapped_result(db, prepared, row["id"], facts[0])
