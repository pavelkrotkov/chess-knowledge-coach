"""Reconstruct bounded standard-start histories for schedule candidates."""

from .style_schedule_budget import BudgetExceeded, GameLimitExceeded
from .style_schedule_game import game_candidates
from .style_schedule_scan_keys import identity, mark_before, record


def read_games(db, games, sequence, *, identities=None):
    candidates, skipped, duplicates, seen = [], 0, 0, set()
    reconstructed = 0
    ordered = games[sequence % len(games) :] + games[: sequence % len(games)] if games else []
    for game, color in ordered:
        dedup, game_key = identity(game, color, identities)
        if dedup in seen:
            duplicates += 1
            continue
        mark_before(identities, game_key, seen, dedup)
        try:
            items = game_candidates(db, game, color)
            record(items, identities, seen, dedup, game_key)
            candidates.extend(items)
            reconstructed += 1
        except GameLimitExceeded:
            skipped += 1
        except BudgetExceeded:
            return candidates, skipped, duplicates, True, reconstructed
        except (ValueError, TypeError, IndexError):
            skipped += 1
    return candidates, skipped, duplicates, False, reconstructed
