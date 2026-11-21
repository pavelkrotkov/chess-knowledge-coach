"""Check the recorded limits of the owned-fork verifier."""

from .fork_proof import MAX_REPLIES
from .objective_provenance import SECONDS


def _branches(detail, anchor):
    proof = detail.get("proof")
    if not isinstance(proof, dict):
        return False
    replies = proof.get("legal_replies")
    return (
        proof.get("minimum_gain") == 3
        and proof.get("move") == detail.get("move")
        and anchor in proof.get("targets", [])
        and type(replies) is int
        and 0 < replies <= MAX_REPLIES
        and isinstance(proof.get("branches"), list)
        and len(proof["branches"]) == replies
    )


def bounds(detail, anchor):
    limits = detail.get("limits")
    if not isinstance(limits, dict):
        return False
    seconds = limits.get("compute_timeout_seconds")
    if type(seconds) not in {int, float} or not 0 < seconds <= SECONDS:
        return False
    if detail["status"] == "incorrect":
        return limits.get("plies") == 3
    return (
        limits.get("reply_limit") == MAX_REPLIES
        and detail.get("reason") == "named_fork_and_gain_proved"
        and detail.get("proven_gain_floor") == 3
        and _branches(detail, anchor)
    )
