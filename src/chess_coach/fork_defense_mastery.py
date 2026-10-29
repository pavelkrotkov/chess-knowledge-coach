"""Gate fork prevention on the qualified source and reconstructed observation."""

from .evidence_review_facts import facts_for_evidence
from .fork_defense_contract import MAPPER, VERSION
from .fork_defense_evidence import _valid, _verify
from .fork_defense_mastery_root import supported_threat


def mastery_allowed(db, row):
    if not _mapping_allowed(row):
        return False
    facts = facts_for_evidence(db, row["id"])
    evidence = dict(row)
    evidence["lifecycle_status"] = "active"
    if len(facts) != 1 or not _valid(evidence, facts[0]):
        return False
    fen = _verify(db, evidence, facts[0])
    return bool(fen and supported_threat(fen, facts[0]["payload"]))


def _mapping_allowed(row):
    return (
        row["fork_defense_fact_count"] == row["link_count"] == 1
        and row["mapping_producer"] == MAPPER
        and row["mapper_version"] == row["run_mapper_version"] == VERSION
        and row["outcome"] in {"success", "failure"}
    )
