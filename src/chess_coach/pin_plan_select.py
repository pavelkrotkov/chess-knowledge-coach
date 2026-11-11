"""Choose one verified recurring pin-defense source."""

from .objective_pin_prevent_contract import VERSION


def _choice(entries):
    games = {item["game_key"] for item, _ in entries}
    failures = list(filter(lambda pair: pair[0]["outcome"] == "failure", entries))
    misses = {item["game_key"] for item, _ in failures}
    if len(games) < 2:
        return None
    if len(misses) >= 2:
        pair = failures[0]
        return 0, pair, len(misses)
    pair = next(filter(lambda pair: pair[0]["outcome"] == "success", entries), None)
    return (1, pair, len(games)) if pair else None


def select(groups):
    choices = [choice for entries in groups.values() if (choice := _choice(entries))]
    if not choices:
        return None
    priority, (item, snapshot), games = min(choices, key=lambda x: (x[0], -x[1][0]["id"]))
    return {
        "evidence_id": item["id"],
        "key": str(item["id"]),
        "version": VERSION,
        "games": games,
        "repeated_miss": priority == 0,
        "named": snapshot["provenance"]["pin_prevention"],
        "color": snapshot["learner_color"],
    }
