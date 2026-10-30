"""Check owned current pin-prevention evidence without changing learning."""

from .evidence_review import inspect_evidence
from .evidence_review_state import _summary, evidence_row
from .learner_identity import normalize_identity
from .pin_evidence_identity import mapper_current
from .pin_pipeline import VERSION


def current(db, evidence_id, subject):
    evidence = _summary(evidence_row(db, evidence_id))
    if not _eligible(evidence, subject) or not mapper_current(db, evidence):
        raise ValueError("pin prevention source unavailable")
    evidence = inspect_evidence(db, evidence_id)
    if evidence["pin_source_currentness"] != "current":
        raise ValueError("pin prevention source stale")
    fact = evidence["facts"][0]
    if not isinstance(fact["payload"].get("proof"), dict):
        raise ValueError("pin prevention proof unavailable")
    return evidence, fact


def _eligible(evidence, subject):
    return (
        _identity(evidence, subject)
        and evidence["skill"] in {"absolute_pin", "relative_pin"}
        and evidence["operation"] == "prevent"
        and evidence["mapping_producer"] == "pin-prevent-mapper"
        and evidence["mapper_version"] == VERSION
        and evidence["outcome"] in {"success", "failure"}
        and evidence["review_status"] in {"accepted", "unreviewed"}
        and evidence["lifecycle_status"] == "active"
    )


def _identity(evidence, subject):
    return bool(evidence["subject"] and normalize_identity(subject) == evidence["subject"])
