"""Read a subject-owned material fact and its immutable source record."""

import json

from .evidence_review import inspect_evidence
from .learner_identity import normalize_identity
from .material_contract import PRODUCER
from .material_policy import MAPPER


def load(db, evidence_id, learner):
    evidence = inspect_evidence(db, evidence_id)
    _check_owner(evidence, learner)
    fact = _fact(evidence)
    source = _source(db, fact["detector_run_id"])
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


def _source(db, detector_run_id):
    record = db.connection.execute(
        "SELECT input_json FROM detector_runs WHERE id=?", (detector_run_id,)
    ).fetchone()
    if record is None:
        raise ValueError("material opportunity unavailable")
    try:
        source = json.loads(record["input_json"])["detector_input"]
    except (ValueError, TypeError, KeyError):
        raise ValueError("material opportunity unavailable") from None
    if not isinstance(source, dict):
        raise ValueError("material opportunity unavailable")
    return source
