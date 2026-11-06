"""Identify and bind a certified unfamiliar fork assessment."""

import json

from .objective_fork_contract import GOAL, OBJECTIVE
from .related_capture_assessment import HISTORY


def is_source(row):
    if row["source_type"] != "corpus" or row["objective"] != GOAL:
        return False
    return bool(json.loads(row["provenance_json"]).get("related_fork", {}).get("assessment"))


def matches(session, data, request):
    if not is_source(session) or session["status"] != "needs_verification":
        return False
    return (
        session["snapshot_hash"] == request["snapshot_hash"]
        and session["learner_color"] == request["learner_color"]
        and data.get("objective_version") == request["objective_version"] == OBJECTIVE
        and data.get("history_mode") == request["history_mode"] == HISTORY
        and data.get("source_fingerprint") == request["source_hash"]
    )
