"""Select and count public pin observations for one indexed branch."""

from .opening_public_pin_coverage import empty
from .opening_public_pin_observe import observe
from .opening_public_proof_coverage import _selected
from .opening_public_proof_source import MAX_GAMES


def branch(db, binding, move, deadline, *, budget, check, charge):
    if binding["control"] == "unknown":
        return {
            "status": "incomplete",
            "reason": "nominal_context_unknown",
            "eligible": None,
            "selected": None,
        }
    found = _selected(db, binding, move, deadline)
    if found is None:
        return {"status": "incomplete", "reason": "deadline", "eligible": None, "selected": None}
    rows, context = found
    selected = rows[:MAX_GAMES]
    result = empty(context, selected, len(rows) > MAX_GAMES, binding)
    budget["branch"] = 0

    observe(db, selected, binding, move, deadline, result, check, charge)
    result["proofs"] = budget["branch"]
    if result["preparation_incomplete"] or result["interrupted"]:
        result["status"] = "incomplete"
    return result
