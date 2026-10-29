"""Bound and reuse per-request game reconstruction."""

from .recurrence_sources import load_game

MAX_REPLAY_GAMES = 20


def source(db, learner, row, sources, cache, excluded):
    game_id = row["game_id"]
    if game_id not in cache:
        if len(cache) >= MAX_REPLAY_GAMES:
            excluded["game replay limit"] += 1
            return None
        cache[game_id] = load_game(db, learner, game_id)
    if cache[game_id] is None:
        excluded["game unavailable or oversized"] += 1
    return cache[game_id]
