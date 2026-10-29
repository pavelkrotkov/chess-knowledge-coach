"""Read a subject-owned material fact and its immutable source record."""

from .evidence_review import inspect_evidence
from .learner_identity import normalize_identity
from .material_contract import PRODUCER
from .material_opportunity_links import valid_link
from .material_opportunity_source import load_source
from .material_policy import MAPPER


def load(db, evidence_id, learner):
    evidence = inspect_evidence(db, evidence_id)
    _check_owner(evidence, learner)
    fact = _fact(evidence)
    if not valid_link(db, evidence, fact):
        raise ValueError("material opportunity unavailable")
    source = load_source(db, fact["detector_run_id"])
    if not isinstance(evidence["context"], dict):
        raise ValueError("material opportunity unavailable")
    return evidence, fact, source


def _check_owner(evidence, learner):
    if evidence["mapping_producer"] != MAPPER or normalize_identity(learner) != evidence["subject"]:
        raise ValueError("material opportunity unavailable")


def _fact(evidence):
    facts = [item for item in evidence["facts"] if item["producer"] == PRODUCER]
    if len(facts) != 1 or not isinstance(facts[0]["payload"], dict):
        raise ValueError("material opportunity unavailable")
    return facts[0]
