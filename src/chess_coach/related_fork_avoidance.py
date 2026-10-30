"""Retrieve supplied defenses against a particular created-by-play fork."""

from . import related_fork_avoidance_contract as contract
from .fact_fingerprint import canonical, digest
from .recurrence_snapshot import read_snapshot
from .related_capture import present
from .related_fork_avoidance_match import scorer
from .related_fork_avoidance_source import source_for_evidence
from .related_fork_prevention_budget import create
from .related_transfer_select import select


def selection(db, subject, evidence_id, corpus_version):
    with read_snapshot(db):
        return _selection(db, subject, evidence_id, corpus_version)


def _selection(db, subject, evidence_id, corpus_version):
    source = source_for_evidence(db, subject, evidence_id)
    budget = create()
    budget["unknown"] = 0
    chosen = select(
        db,
        subject,
        source,
        corpus_version,
        contract.VERSION,
        theme="fork",
        all_lines=True,
        feature=lambda _prompt, _line: dict(source["features"]),
        score=scorer(budget),
    )
    if chosen is None:
        return None
    source, rating, corpus, ordered, scope, diagnostics = chosen
    corpus["avoidance_scan"] = budget
    scope = digest(canonical([scope, contract.VERSION, contract.FILTER_VERSION, budget, ordered]))
    return source, rating, corpus, ordered, scope, diagnostics


def preview(db, subject, evidence_id, corpus_version, cursor=None):
    chosen = selection(db, subject, evidence_id, corpus_version)
    result = present(chosen, cursor)
    for item in result["items"]:
        item.pop("created_witness", None)
        item.pop("defense_role", None)
        item.pop("target_roles", None)
    if chosen is not None:
        result["avoidance_scan"] = chosen[2]["avoidance_scan"]
        result["source_verification"] = (
            "One source-specific currentness recheck uses separately bounded fork scans; "
            "history reconstruction and material-safety checks are additional. The work limits "
            "are not a wall-clock guarantee."
        )
    return result
