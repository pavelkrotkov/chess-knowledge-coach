"""Bound all candidate, anchor and verifier work for one transfer selection."""

LINE_LIMIT = 8
ANCHOR_LIMIT = 64
PROOF_LIMIT = 64


def create():
    return {
        "lines": 0,
        "line_limit": LINE_LIMIT,
        "anchors": 0,
        "anchor_limit": ANCHOR_LIMIT,
        "proofs": 0,
        "proof_limit": PROOF_LIMIT,
        "truncated": False,
    }


def take(budget, name, amount=1):
    if budget[name] + amount > budget[name[:-1] + "_limit"]:
        budget["truncated"] = True
        return False
    budget[name] += amount
    return True
