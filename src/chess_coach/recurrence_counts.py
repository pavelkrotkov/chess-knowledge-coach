"""Count positions and independent games separately."""

from collections import Counter


def _games_for(items, outcome):
    return len({item["game_key"] for item in items if item["outcome"] == outcome})


def counts(items):
    outcomes = Counter(item["outcome"] for item in items)
    games = Counter(item["game_key"] for item in items)
    return {
        "opportunities": len(items),
        "successes": outcomes["success"],
        "misses": outcomes["failure"],
        "ambiguous": outcomes["ambiguous"],
        "independent_games": len(games),
        "games_with_repetitions": sum(n > 1 for n in games.values()),
        "miss_games": _games_for(items, "failure"),
        "success_games": _games_for(items, "success"),
        "review": dict(Counter(item["review"] for item in items)),
        "currentness": dict(Counter(item["currentness"] for item in items)),
    }
