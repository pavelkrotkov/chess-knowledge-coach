"""Recheck fork facts against owned current sources before presenting them."""

from .fork_contract import MAPPER
from .fork_evidence_policy import valid_fact
from .fork_evidence_verify import verified_fen
from .material_opportunity_links import valid_link


def current_fork(
    db,
    evidence,
    *,
    mapper=MAPPER,
    validator=valid_fact,
    verify=verified_fen,
    _history=None,
    _check=None,
):
    if evidence["mapping_producer"] != mapper:
        return None, None, None
    facts = evidence["facts"]
    if (
        len(facts) != 1
        or not validator(evidence, facts[0])
        or not valid_link(db, evidence, facts[0])
    ):
        return {}, "stale", None
    fact = facts[0]
    options = {} if _history is None else {"_history": _history}
    if _check is not None:
        options["_check"] = _check
    fen = verify(db, evidence, fact, **options)
    return fact["payload"], "current" if fen else "stale", fen
