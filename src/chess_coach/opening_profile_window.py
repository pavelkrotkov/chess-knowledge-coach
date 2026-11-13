"""Validate ordered windows and deduplicate each named geometry."""

import json

from .named_structures import definitions
from .opening_profile_play import STORED_PLIES, WINDOW_PLIES


def shapes(rows, first, total, *, limit=WINDOW_PLIES):
    expected = min(limit, total - first + 1, STORED_PLIES - first + 1)
    if expected < 1 or len(rows) != expected:
        raise ValueError("ordered profile window unavailable")
    known = definitions()
    found = set()
    for offset, (ply, encoded) in enumerate(rows):
        if ply != first + offset:
            raise ValueError("ordered profile window differs")
        for family, color in json.loads(encoded):
            if family not in known or color not in {"white", "black"}:
                raise ValueError("ordered profile geometry differs")
            found.add((family, color))
    return found
