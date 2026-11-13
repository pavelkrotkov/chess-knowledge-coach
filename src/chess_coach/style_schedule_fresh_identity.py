"""Treat an overlapping prior context as an ambiguous game identity."""

from .style_schedule_fresh_lookup import MAX_ALIASES, prior


def ambiguous(db, key, games):
    return not games or len(games) > MAX_ALIASES or bool(prior(db, key, games))
