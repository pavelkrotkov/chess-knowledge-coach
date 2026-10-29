"""Check current calculation evidence for short-mate practice."""

from .mate_selection import mapping_skill
from .objective_mate_policy import _run


def eligible(db, evidence, fact):
    try:
        payload = fact["payload"]
        return (
            evidence["skill"] == "calculation"
            and evidence["operation"] == "execute"
            and evidence["outcome"] in {"success", "failure"}
            and evidence["review_status"] in {"accepted", "unreviewed"}
            and _payload(evidence, payload)
            and _run(db, evidence)
        )
    except (KeyError, TypeError, ValueError):
        return False


def _payload(evidence, payload):
    return (
        payload.get("status") == "opportunity"
        and payload.get("outcome") == evidence["outcome"]
        and mapping_skill(payload) == "calculation"
    )
