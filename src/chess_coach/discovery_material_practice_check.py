"""Require current, owned and unrejected material-discovery evidence."""

from .evidence_review import inspect_evidence
from .learner_identity import normalize_identity


def source(db, evidence_id, subject):
    evidence = inspect_evidence(db, evidence_id)
    if (
        evidence["subject"] != normalize_identity(subject)
        or evidence["review_status"] in {"rejected", "revoked"}
        or evidence["discovery_material_currentness"] != "current"
        or evidence["outcome"] != "failure"
    ):
        raise ValueError("discovery material practice unavailable")
    return evidence
