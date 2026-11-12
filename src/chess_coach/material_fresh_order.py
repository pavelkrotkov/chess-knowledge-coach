"""Prioritize newly eligible games and rotate fairly across the recent window."""


def order(games, state):
    ids = [item["game_id"] for item, _color in games]
    progress = dict(state["positions"])
    new = next((game for game in ids if game not in progress), None)
    if new is not None:
        index = ids.index(new)
    elif state["last"] in ids:
        index = (ids.index(state["last"]) + 1) % len(ids)
    else:
        index = 0
    ordered = games[index:] + games[:index]
    positions = [[game, progress.get(game, 0)] for game in ids]
    return ordered, {**state, "positions": positions}


def advance(state, game, ply):
    positions = [[key, ply if key == game else old] for key, old in state["positions"]]
    return {**state, "last": game, "positions": positions}
