"""Choose the latest eligible decision for each game or practice prompt."""

from collections import Counter


def grouped_contexts(items: list[dict], excluded: Counter):
    games: dict[str, dict] = {}
    prompts: dict[str, set[str]] = {}
    training: dict[str, dict] = {}
    for item in items:
        context = item["context"]
        if context["kind"] == "game":
            key = context["game_key"]
            prompts.setdefault(key, set()).add(context["prompt_fen"])
            _select(games, key, item, excluded)
        else:
            _select(training, context["prompt_fen"], item, excluded)
    return games, prompts, training


def _select(groups: dict, key, item: dict, excluded: Counter) -> None:
    previous = groups.get(key)
    if previous is not None:
        excluded["duplicate_context"] += 1
    if previous is None or _rank(item) > _rank(previous):
        groups[key] = item


def _rank(item: dict) -> tuple:
    return item["observed_at"], item["ply"], item["evidence_id"]
