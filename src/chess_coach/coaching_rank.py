"""Rank distinct source-checked patterns by independent failure games."""

from typing import Any

from .lesson_examples import representatives
from .lesson_narrative import build


def rank(db, learner, groups, history):
    candidates: list[dict[str, Any]] = []
    for key, items in groups.items():
        games_seen = {item["game_key"] for item in items}
        if len(games_seen) < 2:
            continue
        skill, operation, family, version = key
        group = {
            "skill": skill,
            "operation": operation,
            "family": family,
            "version": version,
            "lesson_examples": representatives(items),
        }
        lesson = build(db, learner, group, _history=history)
        lesson["examples"] = [item for item in lesson["examples"] if item["lines"]]
        if len(lesson["examples"]) < 2:
            continue
        dates = sorted(item["decision"]["observation_at"][:10] for item in items)
        candidates.append(
            {
                "lesson": lesson,
                "miss_games": len(games_seen),
                "misses": len(items),
                "from_date": dates[0],
                "to_date": dates[-1],
            }
        )
    candidates.sort(
        key=lambda item: (
            -item["miss_games"],
            item["lesson"]["skill"],
            item["lesson"]["operation"],
            item["lesson"]["family"],
        )
    )
    return _distinct(candidates)


def _distinct(candidates):
    selected, seen = [], set()
    for item in candidates:
        lesson = item["lesson"]
        key = (lesson["skill"], lesson["operation"])
        if key not in seen:
            seen.add(key)
            selected.append(item)
    return selected
