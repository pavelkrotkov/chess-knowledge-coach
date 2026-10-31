"""Select bounded source-bound examples of certified pin execution."""

from . import related_pin_contract as contract
from .fact_fingerprint import canonical, digest
from .recurrence_snapshot import read_snapshot
from .related_capture import present
from .related_pin_budget import create
from .related_pin_match import scorer
from .related_pin_source import source_for_evidence
from .related_transfer_select import select


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
        contract.VERSION,
        theme="pin",
        all_lines=True,
        include_objective=True,
        feature=lambda _prompt, _line: dict(source["features"]),
        score=scorer(budget),
    )
    if chosen is None:
        return None
    source, rating, corpus, ordered, scope, diagnostics = chosen
    corpus["pin_scan"] = budget
    scope = digest(canonical([scope, contract.VERSION, contract.FILTER_VERSION, budget, ordered]))
    return source, rating, corpus, ordered, scope, diagnostics


def preview(db, subject, evidence_id, corpus_version, cursor=None):
    chosen = selection(db, subject, evidence_id, corpus_version)
    result = present(chosen, cursor)
    for item in result["items"]:
        item.pop("candidate_certificates", None)
    if chosen is not None:
        result["pin_scan"] = chosen[2]["pin_scan"]
        result["source_verification"] = (
            "Source currentness uses up to two pin-root rechecks with at most eight pin "
            "geometries each. History and material work are separate; limits are not a deadline."
        )
        if result["pin_scan"]["truncated"]:
            result["status"] = "partial: candidate proof budget exhausted"
    return result
