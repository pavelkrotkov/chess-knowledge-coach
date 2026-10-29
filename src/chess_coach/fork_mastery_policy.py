"""Allow only independently qualified fork observations into mastery."""

from .evidence_review_facts import facts_for_evidence
from .fork_contract import MAPPER, VERSION
from .fork_evidence_policy import valid_fact
from .fork_evidence_verify import verified_fen
from .fork_mastery_root import supported_root


def mastery_allowed(db, row):
    if row["skill"] != "fork" and not row["fork_fact_count"] and row["mapping_producer"] != MAPPER:
        return True
    if not _mapping_allowed(row):
        return False
    facts = facts_for_evidence(db, row["id"])
    evidence = dict(row)
    evidence["lifecycle_status"] = "active"
    if len(facts) != 1 or not valid_fact(evidence, facts[0]):
        return False
    fen = verified_fen(db, evidence, facts[0])
    return bool(fen and supported_root(fen, facts[0]["payload"]))


def _mapping_allowed(row):
    return (
        row["fork_fact_count"] == row["link_count"] == 1
        and row["mapping_producer"] == MAPPER
        and row["mapper_version"] == row["run_mapper_version"] == VERSION
        and row["outcome"] in {"success", "failure"}
    )
