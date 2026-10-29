"""Construct an explicit unresolved material observation."""


def ambiguous(kind, reason):
    return {"kind": kind, "outcome": "ambiguous", "reason": reason}
