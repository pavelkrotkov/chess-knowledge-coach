"""Recheck fork facts against owned current sources before presenting them."""

from .fork_contract import MAPPER
from .fork_evidence_policy import valid_fact
from .fork_evidence_verify import verified_fen
from .material_opportunity_links import valid_link


def current_fork(db, evidence):
    if evidence["mapping_producer"] != MAPPER:
        return None, None, None
    facts = evidence["facts"]
    if (
        len(facts) != 1
        or not valid_fact(evidence, facts[0])
        or not valid_link(db, evidence, facts[0])
    ):
        return {}, "stale", None
    fact = facts[0]
    fen = verified_fen(db, evidence, fact)
    return fact["payload"], "current" if fen else "stale", fen
