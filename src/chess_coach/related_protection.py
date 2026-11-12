"""Retrieve a bounded set of operation-matched protection examples."""

from .related_capture import _assessment_options, present
from .related_protection_match import scorer
from .related_protection_source import source_for_evidence
from .related_transfer_select import select

VERSION = "protection-prevent-transfer-v2"
MAX_PROOFS = 32


def selection(db, subject, evidence_id, corpus_version, *, familiar_data=None, check=lambda: None):
    source = source_for_evidence(db, subject, evidence_id)
    budget = {"checked": 0, "limit": MAX_PROOFS, "truncated": False}
    score_candidate = scorer(budget)

    def score(item, source, seen, baseline):
        check()
        return score_candidate(item, source, seen, baseline)

    chosen = select(
        db,
        subject,
        source,
        corpus_version,
        VERSION,
        theme="defensiveMove",
        all_lines=True,
        per_band=2000,
        familiar_data=familiar_data,
        feature=lambda prompt, line: dict(source["features"]),
        score=score,
    )
    if chosen is not None:
        chosen[2]["protection_scan"] = budget
    return chosen


def preview(db, subject, evidence_id, corpus_version, cursor=None):
    chosen = selection(db, subject, evidence_id, corpus_version)
    result = present(chosen, cursor)
    if chosen is not None:
        _assessment_options(db, result["items"], chosen[3], cursor, result["scope"])
        result["source_outcome"] = chosen[0]["outcome"]
        result["protection_scan"] = chosen[2]["protection_scan"]
        result["corpus_limited"] = chosen[2]["limited"]
    return result
