"""Reserve candidate line and pin-root work before inspecting it."""

from .related_pin_contract import LINE_LIMIT, PIN_GEOMETRY_LIMIT, ROOT_PROOF_LIMIT


def create():
    return {
        "lines": 0,
        "line_limit": LINE_LIMIT,
        "root_proofs": 0,
        "root_proof_limit": ROOT_PROOF_LIMIT,
        "pin_geometry_limit": PIN_GEOMETRY_LIMIT,
        "unknown": 0,
        "truncated": False,
    }


def take(budget, kind):
    limit = budget[{"lines": "line_limit", "root_proofs": "root_proof_limit"}[kind]]
    if budget[kind] >= limit:
        budget["truncated"] = True
        return False
    budget[kind] += 1
    return True
