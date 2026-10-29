"""Resolve one current, subject-owned qualified fork-execution observation."""

from .evidence_review import inspect_evidence
from .evidence_review_state import _summary, evidence_row
from .fork_contract import VERSION
from .fork_mastery_root import supported_root
from .material_opportunity_source import load_source
from .related_capture_source import _opening
from .related_fork_source_policy import identity_matches
from .related_fork_witness import witness


def source_for_evidence(db, subject, evidence_id):
    try:
        return _load(db, subject, evidence_id)
    except (TypeError, KeyError, IndexError, AttributeError):
        raise ValueError("fork source unavailable or stale") from None


def _load(db, subject, evidence_id):
    row = evidence_row(db, evidence_id)
    evidence = _summary(row)
    if not identity_matches(db, evidence, subject):
        raise ValueError("fork source unavailable")
    evidence = inspect_evidence(db, evidence_id)
    if evidence["fork_source_currentness"] != "current":
        raise ValueError("fork source unavailable or stale")
    fact = evidence["facts"][0]
    payload = fact["payload"]
    if not supported_root(evidence["decision_fen"], payload):
        raise ValueError("unsupported fork source")
    line = witness(evidence["decision_fen"], payload["proof"])
    source = load_source(db, fact["detector_run_id"])
    reviews = evidence["reviews"]
    return {
        "prompt_fen": evidence["decision_fen"],
        "learner_color": "white" if evidence["decision_fen"].split()[1] == "w" else "black",
        "lines": [line],
        "opening": _opening(db, evidence["position_id"]),
        "outcome": evidence["outcome"],
        "provenance": {
            "evidence_id": evidence_id,
            "position_id": evidence["position_id"],
            "source_fingerprint": source["source_marker"],
            "review_status": evidence["review_status"],
            "review_event_id": reviews[-1]["id"] if reviews else None,
            "detector_run_id": fact["detector_run_id"],
            "fact_id": fact["id"],
            "mapping_run_id": evidence["mapping_run_id"],
            "mapper_version": VERSION,
        },
    }
