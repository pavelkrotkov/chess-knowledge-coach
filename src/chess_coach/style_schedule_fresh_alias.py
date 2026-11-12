"""Check bounded prior targeted aliases against current game identities."""

from .style_schedule_clock import reached
from .style_schedule_fresh_identity import ambiguous
from .style_schedule_fresh_lookup import aliases
from .style_schedule_fresh_lookup import contexts as context_rows


def used(db, key, identities):
    if not identities:
        return set()
    groups, result = context_rows(db, identities)
    for context, current in groups.items():
        if reached():
            return result | current
        games = aliases(db, context)
        if ambiguous(db, key, games):
            result.update(current)
    return result
