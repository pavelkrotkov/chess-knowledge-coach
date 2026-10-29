"""Recheck a candidate before using it as a lesson source."""

from .decision_inspection import inspect_decision
from .evidence_review import inspect_evidence
from .evidence_review_state import evidence_row
from .learner_identity import normalize_identity
from .lesson_source_policy import supported
from .recurrence_review import review

STATES = {
    "material-opportunity-mapper": "material_source_currentness",
    "fork-opportunity-mapper": "fork_source_currentness",
    "fork-defense-mapper": "fork_defense_currentness",
    "bounded-mate-observation-mapper": "mate_source_currentness",
    "pawn-endgame-mapper": "pawn_source_currentness",
    "back-rank-observation-mapper": "back_rank_source_currentness",
    "pawn-structure-lesson-mapper": "pawn_structure_currentness",
}


def source(db, learner, candidate):
    """Return only a current, owned, unrejected source and reconstructed decision."""
    try:
        evidence = inspect_evidence(db, candidate["id"])
        state = STATES.get(evidence["mapping_producer"])
        if not state or evidence[state] != "current":
            return None
        if evidence["subject"] != normalize_identity(learner):
            return None
        if evidence["review_status"] in {"rejected", "revoked"}:
            return None
        if not supported(db, evidence):
            return None
        if evidence["position_id"] != candidate["position_id"]:
            return None
        evidence["lesson_review"] = review(evidence_row(db, evidence["id"]))
        decision = inspect_decision(db, evidence["position_id"], learner=learner)
        return {"evidence": evidence, "decision": decision}
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
