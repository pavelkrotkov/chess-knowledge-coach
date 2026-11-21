"""Read the owner binding of a scheduled unified review."""

import json

from .fact_fingerprint import digest


def _valid_ref(ref):
    return isinstance(ref, list) and len(ref) == 4 and all(isinstance(x, str) and x for x in ref)


def identity(row, subject_hash):
    if row["source_type"] == "puzzle":
        return True, row["source_ref"]
    try:
        ref = json.loads(row["source_ref"])
        if not _valid_ref(ref):
            return False, None
        if digest(ref[0]) != subject_hash:
            return False, None
        return True, ref[1:]
    except (TypeError, ValueError):
        return False, None
