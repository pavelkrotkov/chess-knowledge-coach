"""Read an unassisted, current promotion proof and its entire attempt."""

from .objective_promotion_continue import continuation
from .plan_promotion_events import proof_events
from .plan_promotion_terminal import verified
from .unified_source_current import require_current


def complete(db, session):
    if session["hints_used"] != 0:
        return False
    require_current(db, session)
    evidence = proof_events(db, session)
    if evidence is None:
        return False
    request, result, later = evidence
    if session["status"] == "needs_verification":
        resumed = continuation(db, session)
        return bool(resumed and resumed["complete"])
    if session["status"] == "objective_verified":
        return verified(db, request, result, later)
    return False
