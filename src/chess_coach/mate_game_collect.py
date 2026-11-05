"""Collect and summarize independently replayed game samples."""

from .mate_game_sample import prepared_game
from .mate_game_totals import add, empty

SAMPLE_SIZE = 20


def collect(db, learner, games):
    """Validate and deduplicate in time order, keeping one boundary game."""
    samples, dates, seen = [empty(), empty()], [], set()
    unavailable = duplicates = 0
    for game, _color in games:
        try:
            key, pairs = prepared_game(db, game, learner)
        except (ValueError, TypeError, IndexError):
            unavailable += 1
            continue
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        dates.append(game["projected_start"])
        if len(dates) > 2 * SAMPLE_SIZE:
            break
        add(samples[(len(dates) - 1) // SAMPLE_SIZE], dates[-1], pairs)
    return samples, dates, unavailable, duplicates
