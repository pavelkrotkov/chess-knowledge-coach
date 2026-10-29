"""Group reached positions, played lines, and recurring evidence."""

from collections import Counter, defaultdict


def groups(games):
    positions = {}
    for game in games:
        if game["classification_stale"]:
            continue
        for position in game["opening_positions"]:
            _add_position(positions, game, position)
    return [_group_summary(group) for group in positions.values()]


def _add_position(positions, game, position):
    key = (game["color"], position["key"])
    group = positions.setdefault(
        key,
        {
            "color": key[0],
            "position": key[1],
            "games": [],
            "names": set(),
            "lines": defaultdict(list),
        },
    )
    if all(item["id"] != game["id"] for item in group["games"]):
        group["games"].append(game)
    if game["opening"]["position_key"] == position["key"]:
        opening = game["opening"]
        group["names"].add(f"{opening['eco'] or '?'} {opening['name']}")
    if game["id"] not in group["lines"][position["line"]]:
        group["lines"][position["line"]].append(game["id"])


def _group_summary(group):
    games = group["games"]
    return {
        **group,
        "names": sorted(group["names"]),
        "lines": dict(group["lines"]),
        "count": len(games),
        "outcomes": dict(Counter(g["outcome"] for g in games)),
        "structures": dict(Counter(f for g in games for f in g["structures"]["families"])),
        "structure_coverage": dict(Counter(_structure_status(g) for g in games)),
    }


def _structure_status(game):
    data = game["structures"]
    if data["status"] != "extracted":
        return "not extracted"
    if data["truncated"]:
        return "truncated"
    return "matched" if data["families"] else "no named match"
