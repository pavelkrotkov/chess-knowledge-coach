"""Collapse a practice prompt repeated in a counted game position."""

from collections import Counter

from .mastery_context_selection import grouped_contexts
from .mastery_policy import HALF_LIFE_DAYS


def select_contexts(items: list[dict], excluded: Counter) -> list[dict]:
    games, prompts, training = grouped_contexts(items, excluded)
    seen = set()
    for key, item in games.items():
        if item["confidence"] * 2 ** (-item["age_days"] / HALF_LIFE_DAYS) > 0:
            seen.update(prompts[key])
    result = list(games.values())
    for prompt, item in training.items():
        if prompt in seen:
            excluded["repeated_position"] += 1
        else:
            result.append(item)
    return sorted(result, key=lambda item: item["evidence_id"])
