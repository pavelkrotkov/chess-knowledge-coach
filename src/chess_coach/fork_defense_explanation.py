"""Render a bounded fork-defense observation without inferring intent."""


def explain(fact, fen):
    if not isinstance(fact, dict):
        return None
    threats = fact.get("threats") or []
    anchor = threats[0] if threats else None
    fork = fact.get("fork") or (anchor or {}).get("fork") or {}
    return {
        "outcome": fact.get("outcome"),
        "reason": fact.get("reason"),
        "fen": fen,
        "anchor": anchor,
        "fork": fork,
        "origin": fact.get("threat_origin"),
        "best": _line(fact, "best"),
        "played": _line(fact, "played"),
        "boundary": fact.get("boundary")
        or "Current inputs do not establish a fork-defense outcome.",
        "qualification": "The standstill threat probe is positional, not a game move. Provisional evidence does not establish intent or mastery.",
        "exclusions": "Capturing or checking defenses, promotions, uncertain forks, sacrifices and unresolved counterplay remain ambiguous or outside coverage.",
    }


def _line(fact, role):
    return (fact.get(role) or {}).get("san", [])
