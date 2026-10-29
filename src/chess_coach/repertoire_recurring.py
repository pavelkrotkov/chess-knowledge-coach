"""Find reviewed failures in multiple attributable games."""

from collections import defaultdict


def recurring(games):
    grouped = defaultdict(list)
    for game in games:
        for evidence in game["evidence"]:
            grouped[(evidence["skill"], evidence["operation"])].append(
                {**evidence, "game_id": game["id"]}
            )
    return [
        {"skill": key[0], "operation": key[1], "evidence": values}
        for key, values in grouped.items()
        if len({v["game_id"] for v in values}) >= 2
    ]
