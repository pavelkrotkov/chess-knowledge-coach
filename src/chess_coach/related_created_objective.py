"""Bind one created-exposure first-answer assessment to its exact corpus setup."""

import json

from .objective_created_contract import GOAL, OBJECTIVE
from .related_capture_assessment import HISTORY, setup
from .related_created_assessment import valid
from .related_created_contract import KEY


def is_source(row):
    if row["source_type"] != "corpus" or row["objective"] != GOAL:
        return False
    return bool(json.loads(row["provenance_json"]).get(KEY, {}).get("assessment"))


def apply(snapshot, assessment):
    snapshot["objective"] = GOAL
    snapshot["provenance"].update(
        objective_version=OBJECTIVE,
        history_mode=HISTORY,
        source_fingerprint=assessment["source_fingerprint"],
        objective_target=assessment["target"],
        gain_threshold=3,
    )


def current(db, row, binding, candidate):
    board, _, fingerprint = setup(db, row["source_version"], row["source_key"])
    assessment = binding["assessment"]
    if board.fen() != row["prompt_fen"] or not valid(
        board, fingerprint, assessment, candidate["lines"], binding["created_witness"]
    ):
        raise ValueError("created exposure assessment changed")
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


def apply_filter(snapshot, binding, key):
    if key == KEY and binding and binding.get("assessment"):
        apply(snapshot, binding["assessment"])
