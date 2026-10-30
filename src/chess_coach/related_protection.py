"""Retrieve a bounded set of operation-matched protection examples."""

from .related_capture import present
from .related_protection_match import scorer
from .related_protection_source import source_for_evidence
from .related_transfer_select import select

VERSION = "protection-prevent-transfer-v1"
MAX_PROOFS = 32


def selection(db, subject, evidence_id, corpus_version):
    source = source_for_evidence(db, subject, evidence_id)
    budget = {"checked": 0, "limit": MAX_PROOFS, "truncated": False}
    chosen = select(
        db,
        subject,
        source,
        corpus_version,
        VERSION,
        theme="defensiveMove",
        all_lines=True,
        feature=lambda prompt, line: dict(source["features"]),
        score=scorer(budget),
    )
    if chosen is not None:
        chosen[2]["protection_scan"] = budget
    return chosen


def preview(db, subject, evidence_id, corpus_version, cursor=None):
    chosen = selection(db, subject, evidence_id, corpus_version)
    result = present(chosen, cursor)
    if chosen is not None:
        result["source_outcome"] = chosen[0]["outcome"]
        result["protection_scan"] = chosen[2]["protection_scan"]
    return result
