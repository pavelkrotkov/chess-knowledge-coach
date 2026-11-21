"""Recheck a candidate before using it as a lesson source."""

from .decision_inspection import inspect_decision
from .evidence_review import inspect_evidence
from .evidence_review_state import evidence_row
from .learner_identity import normalize_identity
from .lesson_source_policy import supported
from .lesson_source_states import STATES
from .recurrence_review import review


def source(db, learner, candidate, *, _history=None, check=None):
    """Return only a current, owned, unrejected source and reconstructed decision."""
    try:
        if _history is not None and (_history.db is not db or _history.learner != learner):
            raise ValueError("lesson history scope differs")
        # Fork currentness can require CPU proof work inside evidence inspection.
        evidence = _evidence(db, candidate["id"], _history, check)
        if not _allowed(db, learner, candidate, evidence, _history):
            return None
        evidence["lesson_review"] = review(evidence_row(db, evidence["id"]))
        decision = inspect_decision(db, evidence["position_id"], learner=learner, _history=_history)
        return {"evidence": evidence, "decision": decision}
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def _allowed(db, learner, candidate, evidence, history):
    state = STATES.get(evidence["mapping_producer"])
    return bool(
        state
        and evidence[state] == "current"
        and evidence["subject"] == normalize_identity(learner)
        and evidence["review_status"] not in {"rejected", "revoked"}
        and _supported_source(db, evidence, history)
        and evidence["position_id"] == candidate["position_id"]
    )


def _supported_source(db, evidence, history):
    if history is None:
        return supported(db, evidence)
    return supported(db, evidence, _history=history)


def _evidence(db, evidence_id, history, check):
    options = {} if history is None else {"_history": history}
    if check is not None:
        options["_fork_check"] = check
    return inspect_evidence(db, evidence_id, **options)
