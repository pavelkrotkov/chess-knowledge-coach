"""Explain the scope and a branch of a provisional pin observation."""


def explain(fact, fen):
    if not isinstance(fact, dict):
        return None
    proof = fact.get("proof") or {}
    branches = proof.get("branches") or []
    return {
        "fen": fen,
        "kind": fact.get("kind"),
        "outcome": fact.get("outcome"),
        "reason": fact.get("reason"),
        "proof": proof,
        "geometry": fact.get("geometry"),
        "sample": branches[0] if branches else None,
        "alternative": fact.get("alternative"),
        "trigger": fact.get("trigger"),
        "boundary": proof.get("boundary", "No bounded consequence was proved")
        + "; later counterplay and compensation remain unresolved.",
        "qualification": "Provisional observation, not a claim about intent or mastery.",
    }
