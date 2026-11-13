"""Check the exact current owned discovery-defense source."""

from .evidence_review import inspect_evidence
from .learner_identity import normalize_identity


def source(db, evidence_id, subject):
    evidence = inspect_evidence(db, evidence_id)
    if (
        evidence["subject"] != normalize_identity(subject)
        or evidence["review_status"] in {"rejected", "revoked"}
        or evidence["discovery_defense_currentness"] != "current"
        or evidence["outcome"] != "failure"
    ):
        raise ValueError("discovery defense unavailable")
    return evidence
