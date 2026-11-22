"""Select independently matched games and account for prevention coverage."""

from .opening_public_prevention_coverage import ORIGINS, empty, finish
from .opening_public_prevention_observe import observe
from .opening_public_proof_coverage import _selected
from .opening_public_proof_source import MAX_GAMES


def _unavailable(reason):
    return {"status": "incomplete", "reason": reason, "eligible": None, "selected": None}


def branch(db, binding, move, deadline, *, start, budget, check, charge):
    if binding["control"] == "unknown":
        return _unavailable("nominal_context_unknown")
    found = _selected(db, binding, move, deadline)
    if found is None:
        return _unavailable("deadline")
    rows, context = found
    selected = rows[:MAX_GAMES]
    result = {
        "status": "prepared",
        "eligible": context["matched_candidates"],
        "excluded_context": context["excluded_context"],
        "unknown_context": context["unknown_context"],
        "selected": len(selected),
        "more_eligible": len(rows) > MAX_GAMES,
        "censored": 0,
        "interrupted": False,
        "proof_limit": False,
        "origins": {origin: empty() for origin in ORIGINS},
    }
    observe(db, selected, binding, move, deadline, start, budget, check, charge, result)
    return finish(result)
