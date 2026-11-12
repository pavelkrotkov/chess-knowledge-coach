"""Check bounded prior targeted aliases against current game identities."""

from .style_schedule_clock import reached
from .style_schedule_fresh_identity import resolve
from .style_schedule_fresh_lookup import MAX_ALIASES, aliases, prior
from .style_schedule_fresh_lookup import contexts as context_rows


def used(db, key, identities):
    if not identities:
        return set()
    groups, result = context_rows(db, identities)
    for context, current in groups.items():
        if reached():
            return result | current
        games = aliases(db, context)
        if len(games) > MAX_ALIASES:
            result.update(current)
            continue
        for game_id in prior(db, key, games):
            try:
                value = identities.get(game_id) or resolve(db, game_id)
                result.add(value)
            except (ValueError, TypeError, IndexError):
                result.update(current)
    return result
