"""Select bounded source-bound examples of certified pin execution."""

from . import related_pin_contract as contract
from .fact_fingerprint import canonical, digest
from .recurrence_snapshot import read_snapshot
from .related_capture import present
from .related_pin_budget import create
from .related_pin_match import scorer
from .related_pin_source import source_for_evidence
from .related_transfer_select import select


def selection(db, subject, evidence_id, corpus_version, mechanism=None):
    with read_snapshot(db):
        return _selection(db, subject, evidence_id, corpus_version, mechanism)


def _selection(db, subject, evidence_id, corpus_version, mechanism):
    source = source_for_evidence(db, subject, evidence_id, mechanism)
    budget = create()
    version = contract.transfer_version(source)
    chosen = select(
        db,
        subject,
        source,
        corpus_version,
        version,
        theme="defensiveMove" if contract.operation(version) == "prevent" else "pin",
        all_lines=True,
        include_objective=True,
        feature=lambda _prompt, _line: dict(source["features"]),
        score=scorer(budget),
    )
    if chosen is None:
        return None
    source, rating, corpus, ordered, scope, diagnostics = chosen
    corpus["pin_scan"] = budget
    scope = digest(canonical([scope, version, contract.filter_version(version), budget, ordered]))
    return source, rating, corpus, ordered, scope, diagnostics


def preview(db, subject, evidence_id, corpus_version, cursor=None, mechanism=None):
    try:
        chosen = selection(db, subject, evidence_id, corpus_version, mechanism)
    except contract.UnsupportedPinTransfer:
        return {
            "status": (
                "This source has no supported pin slide."
                if mechanism == "slide"
                else "This source has no supported capture or pin-prevention contrast."
            ),
            "items": [],
        }
    result = present(chosen, cursor)
    for item in result["items"]:
        item.pop("candidate_certificates", None)
    if chosen is not None:
        from .related_pin_preview import details

        details(result, chosen)
    return result
