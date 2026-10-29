"""Turn a material fact into a plain, carefully bounded review explanation."""


def explain_material(context):
    fact = context.get("material_observation") if isinstance(context, dict) else None
    if not isinstance(fact, dict):
        return None
    kind = fact.get("kind")
    outcome = fact.get("outcome")
    summary = _summary(kind, outcome)
    return {
        "summary": summary,
        "target": fact.get("target"),
        "piece": fact.get("target_piece"),
        "reason": fact.get("reason"),
        "best": (fact.get("best") or {}).get("san", []),
        "played": (fact.get("played") or {}).get("san", []),
        "boundary": fact.get("boundary")
        or "The current inputs do not establish a bounded outcome.",
        "qualification": "These are short bounded observations, not proof against all tactics or compensation. They do not establish intent or mastery and are awaiting independent validation.",
        "exclusions": "Pawn captures, checks, en passant, promotion, recaptures, sacrifices and unresolved lines are outside coverage or ambiguous.",
    }


def _summary(kind, outcome):
    if outcome == "ambiguous":
        return "The material opportunity is unresolved under these checks."
    if kind == "material_protection":
        return (
            "The played continuation avoids the tested immediate material capture."
            if outcome == "success"
            else "The played continuation includes the tested capture of the exposed piece."
        )
    return (
        "The played continuation captures the tested material."
        if outcome == "success"
        else "The tested best continuation captures material that the played line does not capture within the displayed line."
    )
