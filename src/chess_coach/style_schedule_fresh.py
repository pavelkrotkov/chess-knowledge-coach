"""Prefer independent early choices without existing purpose work."""

from .style_schedule_fresh_history import read


def _unused(candidates, positions, used):
    return [
        item
        for item in candidates
        if item["position_id"] not in positions and item.get("_game_key") not in used
    ]


def available(db, key, candidates, identities):
    if not candidates:
        return []
    positions = {item["position_id"] for item in candidates}
    games = set(identities) | {item["game_id"] for item in candidates}
    history = read(db, key, positions, games)
    if history is None:
        return []
    positions_used, games_used = history
    used = {identity for game, identity in identities.items() if game in games_used}
    return _unused(candidates, positions_used, used)
