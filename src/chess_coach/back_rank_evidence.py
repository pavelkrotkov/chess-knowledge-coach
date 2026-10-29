"""Resolve current, subject-owned back-rank evidence and fact lineage."""

from .back_rank_contract import MAPPER
from .back_rank_evidence_valid import recorded_key, valid
from .back_rank_inputs import inputs
from .back_rank_replay import replay
from .evidence_review_facts import facts_for_evidence
from .evidence_review_state import _summary, evidence_row
from .learner_identity import normalize_identity
from .mate_inspection_source import position_row


def load(db, evidence_id, learner):
    evidence = _summary(evidence_row(db, evidence_id))
    if evidence["mapping_producer"] != MAPPER or normalize_identity(learner) != evidence["subject"]:
        raise ValueError("back-rank opportunity unavailable")
    facts = facts_for_evidence(db, evidence_id)
    evidence["facts"] = facts
    if len(facts) != 1 or not valid(db, evidence, facts[0]):
        raise ValueError("back-rank opportunity unavailable")
    fact = facts[0]
    position = position_row(db, evidence["position_id"])
    _, key, _ = inputs(db, position, learner)
    recorded = recorded_key(db, fact)
    if key != recorded or not replay(db, position["id"], key, evidence["subject"]):
        raise ValueError("back-rank opportunity stale")
    return evidence, fact, key


def currentness(db, evidence):
    if evidence["mapping_producer"] != MAPPER:
        return None
    try:
        load(db, evidence["id"], evidence["subject"])
    except (ValueError, TypeError, KeyError):
        return "stale"
    return "current"
