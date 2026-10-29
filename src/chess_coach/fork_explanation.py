"""Describe a provisional fork without implying intent or recognition."""


def explain_fork(fact, fen):
    if not isinstance(fact, dict):
        return None
    proof = fact.get("proof") or {}
    branches = proof.get("branches") or []
    return {
        "outcome": fact.get("outcome"),
        "reason": fact.get("reason"),
        "move": proof.get("san"),
        "targets": proof.get("targets", []),
        "reply_count": proof.get("legal_replies"),
        "sample": branches[0] if branches else None,
        "fen": fen,
        "best": (fact.get("best") or {}).get("san", []),
        "played": (fact.get("played") or {}).get("san", []),
        "boundary": proof.get("boundary")
        or "The current inputs do not establish a bounded fork outcome.",
        "qualification": "Provisional bounded observation; it does not prove recognition, mastery, or the absence of later counterplay.",
        "exclusions": "Capturing fork moves, mate-only consequences, recaptures, promotions, unresolved checks, sacrifices and forcing counterplay remain outside coverage or ambiguous.",
    }
