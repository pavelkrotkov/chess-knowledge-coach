"""Produce unresolved fork observations."""


def ambiguous(reason):
    return {"kind": "fork", "outcome": "ambiguous", "reason": reason}
