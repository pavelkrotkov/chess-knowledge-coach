"""Resolve a current owned mate observation using its original mapper semantics."""

from .mate_evidence import load
from .objective_contract import VERSION as IMMEDIATE_VERSION
from .objective_mate_policy import eligible as immediate_eligible
from .objective_mate_source import resolve as immediate_source
from .objective_short_policy import eligible as short_eligible
from .objective_short_source import VERSION as SHORT_VERSION
from .objective_short_source import resolve as short_source
from .related_capture_source import _opening


def source_for_evidence(db, subject, evidence_id):
    evidence, fact, _ = load(db, evidence_id, subject)
    if immediate_eligible(db, evidence, fact):
        source = immediate_source(db, IMMEDIATE_VERSION, str(evidence_id), subject)
    elif short_eligible(db, evidence, fact):
        source = short_source(db, SHORT_VERSION, str(evidence_id), subject)
    else:
        raise ValueError("mate source unavailable or unsupported")
    source["opening"] = _opening(db, evidence["position_id"])
    source["outcome"] = evidence["outcome"]
    source["provenance"].update(
        fact_id=fact["id"],
        mapping_run_id=evidence["mapping_run_id"],
        mapper_version=evidence["mapper_version"],
        operation=evidence["operation"],
    )
    if load(db, evidence_id, subject) != (
        evidence,
        fact,
        source["provenance"]["source_fingerprint"],
    ):
        raise ValueError("mate source changed")
    return source
