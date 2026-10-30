"""Reconstruct bounded standard-start histories for schedule candidates."""

import hashlib

from .style_schedule_budget import BudgetExceeded, GameLimitExceeded
from .style_schedule_game import game_candidates


def read_games(db, games, sequence):
    candidates, skipped, duplicates, seen = [], 0, 0, set()
    reconstructed = 0
    ordered = games[sequence % len(games) :] + games[: sequence % len(games)] if games else []
    for game, color in ordered:
        identity = hashlib.sha256((game["pgn"] + color).encode()).digest()
        if identity in seen:
            duplicates += 1
            continue
        seen.add(identity)
        try:
            candidates.extend(game_candidates(db, game, color))
            reconstructed += 1
        except GameLimitExceeded:
            skipped += 1
        except BudgetExceeded:
            return candidates, skipped, duplicates, True, reconstructed
        except (ValueError, TypeError, IndexError):
            skipped += 1
    return candidates, skipped, duplicates, False, reconstructed
