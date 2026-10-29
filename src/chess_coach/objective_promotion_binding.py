"""Bind an explicit public promotion source to its request."""

from .objective_contract import STANDALONE
from .objective_promotion_contract import OBJECTIVES as PROMOTION_OBJECTIVES
from .objective_promotion_contract import VERSION as PROMOTION_VERSION


def public_scope(session, request):
    return (
        session["source_type"] == "public"
        and session["objective"] in PROMOTION_OBJECTIVES
        and session["status"] == "needs_verification"
        and session["snapshot_hash"] == request["snapshot_hash"]
        and session["learner_color"] == request["learner_color"]
    )


def public_binding(data, request):
    return (
        data.get("objective_version") == request["objective_version"] == PROMOTION_VERSION
        and data.get("history_mode") == request["history_mode"] == STANDALONE
        and data.get("source_fingerprint") == request["source_hash"]
    )
