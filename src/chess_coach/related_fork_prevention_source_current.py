"""Load an owned defense fact and independently reverify its current source."""

from .evidence_review_facts import facts_for_evidence
from .evidence_review_state import _summary, evidence_row
from .fork_defense_evidence import current_defense
from .fork_defense_mastery_root import supported_threat
from .related_fork_prevention_policy import identity_matches


def current(db, subject, evidence_id):
    evidence = _summary(evidence_row(db, evidence_id))
    if not identity_matches(db, evidence, subject):
        raise ValueError("fork prevention source unavailable")
    evidence["facts"] = facts_for_evidence(db, evidence_id)
    _, status, fen = current_defense(db, evidence)
    if status != "current":
        raise ValueError("fork prevention source unavailable or stale")
    evidence["decision_fen"] = fen
    if not supported_threat(fen, evidence["facts"][0]["payload"]):
        raise ValueError("unsupported knight threat")
    return evidence
