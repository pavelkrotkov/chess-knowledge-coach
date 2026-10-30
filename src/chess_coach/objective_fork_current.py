"""Load exact current qualified fork evidence and its mapping scope."""

from .evidence_review import inspect_evidence
from .evidence_review_state import _summary, evidence_row
from .fork_contract import MAPPER, VERSION
from .fork_mastery_root import supported_root
from .learner_identity import normalize_identity
from .objective_fork_mapping import matches as mapping_matches


def current(db, evidence_id, subject):
    evidence = _summary(evidence_row(db, evidence_id))
    if not _eligible(evidence, subject) or not mapping_matches(db, evidence):
        raise ValueError("fork objective unavailable")
    evidence = inspect_evidence(db, evidence_id)
    if evidence["fork_source_currentness"] != "current":
        raise ValueError("fork source unavailable or stale")
    fact = evidence["facts"][0]
    if not supported_root(evidence["decision_fen"], fact["payload"]):
        raise ValueError("unsupported fork source")
    return evidence, fact


def _eligible(evidence, subject):
    return (
        _identity(evidence, subject)
        and evidence["skill"] == "fork"
        and evidence["operation"] == "execute"
        and evidence["mapping_producer"] == MAPPER
        and evidence["mapper_version"] == VERSION
        and evidence["outcome"] in {"success", "failure"}
        and evidence["review_status"] in {"accepted", "unreviewed"}
        and evidence["lifecycle_status"] == "active"
    )


def _identity(evidence, subject):
    return bool(evidence["subject"] and normalize_identity(subject) == evidence["subject"])
