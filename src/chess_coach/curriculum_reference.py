"""Decode only unambiguous versioned puzzle references."""

import json


def reference(value: str) -> tuple[str, str] | None:
    try:
        ref = json.loads(value)
    except (TypeError, ValueError):
        return None
    if not isinstance(ref, list) or len(ref) != 2 or not all(isinstance(x, str) and x for x in ref):
        return None
    return ref[0], ref[1]
