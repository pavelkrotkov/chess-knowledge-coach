"""Rotate structural targets independently of the fallback cursor."""

from .style_schedule_candidates_rank import rank


def choose(key, sequence, candidates):
    games = {}
    for item in candidates:
        games.setdefault(item["game_id"], []).append(item)
    ordered = sorted(games, key=lambda game: rank(key, "structural", game, 0))
    step = sequence // 2
    game = ordered[step % len(ordered)]
    positions = sorted(
        games[game], key=lambda item: rank(key, "structural", game, item["position_id"])
    )
    return positions[(step // len(ordered)) % len(positions)]


def independent(targets, candidates):
    center_games = {item["game_id"] for item in candidates if item.get("early_center")}
    if len(center_games) != 1:
        return targets
    game = next(iter(center_games))
    separate = [item for item in targets if item["game_id"] != game and item["status"] == "ready"]
    return separate or targets
