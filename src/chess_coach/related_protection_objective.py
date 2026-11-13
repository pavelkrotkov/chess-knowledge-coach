"""Bind a certified corpus defense to the objective worker."""

import json

from .objective_protection_contract import OBJECTIVE
from .related_capture_assessment import HISTORY, setup
from .related_protection_assessment import valid
from .related_protection_assessment_novelty import require_novel


def is_source(row):
    if row["source_type"] != "corpus" or row["objective"] != "protect_threatened_piece":
        return False
    return bool(json.loads(row["provenance_json"]).get("related_protection", {}).get("assessment"))


def apply(snapshot, assessment):
    snapshot["objective"] = "protect_threatened_piece"
    snapshot["provenance"].update(
        objective_version=OBJECTIVE,
        history_mode=HISTORY,
        source_fingerprint=assessment["source_fingerprint"],
        objective_target=assessment["target"],
        gain_threshold=assessment["gain_threshold"],
    )


def current(db, row, binding, candidate):
    board, _, fingerprint = setup(db, row["source_version"], row["source_key"])
    assessment = binding["assessment"]
    if board.fen() != row["prompt_fen"] or not valid(
        board, fingerprint, assessment, binding["objective_target"], candidate["lines"]
    ):
        raise ValueError("protection assessment changed")
    require_novel(db, row)
    apply(candidate, assessment)


def matches(session, data, request):
    return (
        is_source(session)
        and session["status"] == "needs_verification"
        and session["snapshot_hash"] == request["snapshot_hash"]
        and session["learner_color"] == request["learner_color"]
        and data.get("objective_version") == request["objective_version"] == OBJECTIVE
        and data.get("history_mode") == request["history_mode"] == HISTORY
        and data.get("source_fingerprint") == request["source_hash"]
    )


def apply_filter(snapshot, binding, binding_key):
    if binding_key == "related_protection" and binding and binding.get("assessment"):
        apply(snapshot, binding["assessment"])
