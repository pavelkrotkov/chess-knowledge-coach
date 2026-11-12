"""Keep targeted controls independent when their game identity is known."""


def independent(targets, candidates):
    center_games = {_identity(item) for item in candidates if item.get("early_center")}
    center_games.discard(None)
    if len(center_games) != 1:
        return targets
    game = next(iter(center_games))
    separate = [item for item in targets if _separate(item, game)]
    return separate or targets


def controls(candidates, target, reserved):
    if target is None:
        return candidates
    result = [item for item in candidates if item["game_id"] != target["game_id"]]
    if not reserved:
        return result
    key = target.get("_game_key")
    return [item for item in result if _distinct(item, key)] if key else []


def _identity(item):
    return item.get("_game_key", item["game_id"])


def _separate(item, game):
    identity = _identity(item)
    return identity is not None and identity != game and item["status"] == "ready"


def _distinct(item, key):
    other = item.get("_game_key")
    return other is not None and other != key
