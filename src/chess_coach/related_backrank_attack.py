"""Retrieve supplied witnesses for one selected back-rank attacking root."""

from . import related_backrank_contract as contract
from .fact_fingerprint import canonical, digest
from .recurrence_snapshot import read_snapshot
from .related_backrank_features import features
from .related_backrank_match import scorer
from .related_backrank_source import source_for_evidence
from .related_capture import present
from .related_transfer_select import select


def selection(db, subject, evidence_id, corpus_version, root_move):
    with read_snapshot(db):
        source = source_for_evidence(db, subject, evidence_id, root_move)
        budget = {"lines": 0, "line_limit": contract.LINE_LIMIT, "truncated": False}
        chosen = select(
            db,
            subject,
            source,
            corpus_version,
            contract.VERSION,
            theme="mateIn1" if source["objective"] == "mate_in_one" else "mateIn2",
            all_lines=True,
            include_objective=True,
            feature=features,
            score=scorer(budget),
        )
        if chosen is None:
            return None
        source, rating, corpus, ordered, scope, diagnostics = chosen
        corpus["backrank_scan"] = budget
        scope = digest(
            canonical(
                [scope, contract.VERSION, contract.FILTER_VERSION, root_move, budget, ordered]
            )
        )
        return source, rating, corpus, ordered, scope, diagnostics


def preview(db, subject, evidence_id, corpus_version, root_move, cursor=None):
    chosen = selection(db, subject, evidence_id, corpus_version, root_move)
    result = present(chosen, cursor)
    if chosen is not None:
        result["source_outcome"] = chosen[0]["outcome"]
        result["mate_timing"] = chosen[0]["objective"]
        result["backrank_scan"] = chosen[2]["backrank_scan"]
    return result
