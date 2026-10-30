"""Load only current, qualified owned pin-execution evidence."""

from .evidence_review import inspect_evidence
from .evidence_review_state import _summary, evidence_row
from .learner_identity import normalize_identity
from .pin_evidence_identity import mapper_current
from .pin_pipeline import VERSION


def current(db, evidence_id, subject):
    evidence = _summary(evidence_row(db, evidence_id))
    if not _eligible(evidence, subject) or not mapper_current(db, evidence):
        raise ValueError("pin objective unavailable")
    evidence = inspect_evidence(db, evidence_id)
    if evidence["pin_source_currentness"] != "current":
        raise ValueError("pin source unavailable or stale")
    fact = evidence["facts"][0]
    if not isinstance(fact["payload"].get("proof"), dict):
        raise ValueError("pin proof unavailable")
    return evidence, fact


def _eligible(evidence, subject):
    return (
        _identity(evidence, subject)
        and evidence["skill"] in {"absolute_pin", "relative_pin"}
        and evidence["operation"] == "execute"
        and evidence["mapping_producer"] == "pin-execute-mapper"
        and evidence["mapper_version"] == VERSION
        and evidence["outcome"] == "success"
        and evidence["review_status"] in {"accepted", "unreviewed"}
        and evidence["lifecycle_status"] == "active"
    )


def _identity(evidence, subject):
    return bool(evidence["subject"] and normalize_identity(subject) == evidence["subject"])
