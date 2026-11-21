"""Bound and reuse per-request game reconstruction."""

from .recurrence_sources import load_game

MAX_REPLAY_GAMES = 20


def source(db, learner, row, sources, cache, excluded, *, _history=None):
    game_id = row["game_id"]
    if game_id not in cache:
        if len(cache) >= MAX_REPLAY_GAMES:
            excluded["game replay limit"] += 1
            return None
        if _history is None or not _history.can_share(db, learner, game_id, row["position_id"]):
            cache[game_id] = load_game(db, learner, game_id)
        else:
            cache[game_id] = load_game(
                db, learner, game_id, _history=_history, _position_id=row["position_id"]
            )
    if cache[game_id] is None:
        excluded["game unavailable or oversized"] += 1
    return cache[game_id]
