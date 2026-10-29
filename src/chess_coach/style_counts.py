"""Count independent games and sample choices without skill inference."""

from collections import Counter

MIN_OPPORTUNITIES = 5
MIN_GAMES = 3


def counts(items, dimension):
    votes = [item for item in items if item["choices"][dimension] not in (None, "ambiguous")]
    counts = Counter(item["choices"][dimension] for item in votes)
    games = len({item["game_id"] for item in votes})
    enough = len(votes) >= MIN_OPPORTUNITIES and games >= MIN_GAMES
    kinds = Counter(item["choices"][dimension] for item in items)
    return {
        "opportunities": len(votes),
        "games": games,
        "choices": dict(counts),
        "ambiguous": kinds["ambiguous"],
        "no_contrast": kinds[None],
        "sufficient": enough,
        "direction": _direction(counts) if enough else None,
    }


def _direction(counts):
    values = counts.most_common()
    if not values or (len(values) > 1 and values[0][1] == values[1][1]):
        return "balanced"
    return values[0][0]
