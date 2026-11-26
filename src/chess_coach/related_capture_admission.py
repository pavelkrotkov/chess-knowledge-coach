"""Admit current capture sources and resolve opaque transfer references."""

from .evidence_review_state import _with_facts, evidence_row
from .material_policy import fact_allowed


def admit(db, subject, position, corpus_version, reference):
    from .related_capture import VERSION, _selection
    from .related_transfer_admission import admit as admit_selection

    selection = _selection(db, subject, position, corpus_version)
    return admit_selection(selection, reference, VERSION, "material_capture")


def eligible_metadata(db, evidence_id):
    evidence = _with_facts(db, evidence_row(db, evidence_id))
    if (
        evidence["lifecycle_status"] != "active"
        or evidence["review_status"] not in {"accepted", "unreviewed"}
        or evidence["outcome"] != "failure"
    ):
        return False
    facts = evidence["facts"]
    if len(facts) != 1:
        return False
    fact = facts[0]
    return (
        fact["detector_status"] == "active"
        and fact_allowed(
            fact,
            skill=evidence["skill"],
            operation=evidence["operation"],
            outcome=evidence["outcome"],
        )
        and fact["payload"].get("kind") == "material_capture"
    )
