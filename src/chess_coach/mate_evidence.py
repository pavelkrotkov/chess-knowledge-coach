"""Read owned, current bounded mate evidence and its source lineage."""

import json

from .evidence_review_facts import facts_for_evidence
from .evidence_review_state import _summary, evidence_row
from .learner_identity import normalize_identity
from .mate_auto_replay import replay
from .mate_contract import MAPPER
from .mate_evidence_valid import valid
from .mate_inspection_source import position_row, source


def load(db, evidence_id, learner):
    evidence = _summary(evidence_row(db, evidence_id))
    if evidence["mapping_producer"] != MAPPER or normalize_identity(learner) != evidence["subject"]:
        raise ValueError("mate opportunity unavailable")
    facts = facts_for_evidence(db, evidence_id)
    if len(facts) != 1:
        raise ValueError("mate opportunity unavailable")
    fact = facts[0]
    evidence["facts"] = facts
    if not valid(db, evidence, fact):
        raise ValueError("mate opportunity unavailable")
    position = position_row(db, evidence["position_id"])
    _, fingerprint = source(db, position, learner)
    row = db.connection.execute(
        "SELECT input_json FROM detector_runs WHERE id=?", (fact["detector_run_id"],)
    ).fetchone()
    try:
        recorded = json.loads(row["input_json"])["detector_input"]["source_fingerprint"]
    except (TypeError, ValueError, KeyError):
        raise ValueError("mate opportunity unavailable") from None
    if fingerprint != recorded or not replay(
        db, evidence["position_id"], fingerprint, evidence["subject"]
    ):
        raise ValueError("mate opportunity stale")
    return evidence, fact, fingerprint


def currentness(db, evidence):
    if evidence["mapping_producer"] != MAPPER:
        return None
    try:
        load(db, evidence["id"], evidence["subject"])
    except (ValueError, TypeError, KeyError):
        return "stale"
    return "current"
