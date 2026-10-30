"""Retrieve bounded source-linked anchored knight-fork defenses."""

from . import related_fork_prevention_contract
from .fact_fingerprint import canonical, digest
from .recurrence_snapshot import read_snapshot
from .related_capture import present
from .related_fork_prevention_budget import create
from .related_fork_prevention_match import scorer
from .related_fork_prevention_source import source_for_evidence
from .related_transfer_select import select

VERSION = "anchored-knight-fork-prevention-v1"


def selection(db, subject, evidence_id, corpus_version):
    with read_snapshot(db):
        return _selection(db, subject, evidence_id, corpus_version)


def _selection(db, subject, evidence_id, corpus_version):
    source = source_for_evidence(db, subject, evidence_id)
    budget = create()
    chosen = select(
        db,
        subject,
        source,
        corpus_version,
        VERSION,
        theme="fork",
        all_lines=True,
        feature=lambda _prompt, _line: dict(source["features"]),
        score=scorer(budget),
    )
    if chosen is None:
        return None
    source, rating, corpus, ordered, scope, diagnostics = chosen
    corpus["prevention_scan"] = budget
    scope = digest(
        canonical(
            [scope, VERSION, related_fork_prevention_contract.FILTER_VERSION, budget, ordered]
        )
    )
    return source, rating, corpus, ordered, scope, diagnostics


def preview(db, subject, evidence_id, corpus_version, cursor=None):
    chosen = selection(db, subject, evidence_id, corpus_version)
    result = present(chosen, cursor)
    for item in result["items"]:
        item.pop("defense_role", None)
        item.pop("target_roles", None)
    if chosen is not None:
        result["source_outcome"] = chosen[0]["outcome"]
        result["prevention_scan"] = chosen[2]["prevention_scan"]
        result["source_verification"] = (
            "One source-specific currentness recheck, separately bounded by up to 64 anchor "
            "moves and 32 anchor proofs plus one or two scans of up to 16 fork candidates; "
            "source history reconstruction and material-safety checks are additional. These are fork-proof bounds, not a wall-clock guarantee."
        )
    return result
