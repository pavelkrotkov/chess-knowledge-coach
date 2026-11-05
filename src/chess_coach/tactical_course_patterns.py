"""Revalidate and assemble a small ordered set of tactical patterns."""

from .tactical_course_budget import PreviewUnavailable
from .tactical_course_chapters import challenge
from .tactical_course_resolve import own, related

MAX_PATTERNS = 3


def _pattern(group, choice, bindings):
    lesson = group["lesson"]
    return {
        "skill": lesson["skill"],
        "operation": lesson["operation"],
        "family": lesson["family"],
        "kind": choice["kind"],
        "independent_games": len({item["game_key"] for item in bindings}),
        "supporting_sources": bindings,
        "inspected_misses": group["misses"],
        "review_states": [item["review"] for item in lesson["examples"]],
        "local_challenge": challenge(choice),
    }


def assemble(db, subject, corpus, groups, budget):
    patterns, chapters, unavailable = [], [], []
    for index, group in enumerate(groups):
        if len(patterns) >= MAX_PATTERNS:
            return patterns, chapters, unavailable, len(groups) - index
        result = own(db, subject, group, budget)
        if result is None:
            unavailable.append(
                {
                    "skill": group["lesson"]["skill"],
                    "operation": group["lesson"]["operation"],
                    "reason": "owned source unavailable",
                }
            )
            continue
        choice, own_chapter, bindings = result
        patterns.append(_pattern(group, choice, bindings))
        chapters.append(own_chapter)
        item, reason = related(db, subject, corpus, choice, budget)
        if item is None:
            unavailable.append(
                {
                    "skill": group["lesson"]["skill"],
                    "operation": group["lesson"]["operation"],
                    "reason": reason,
                }
            )
        else:
            chapters.append(item)
    if not patterns:
        raise PreviewUnavailable("no supported recurring patterns")
    return patterns, chapters, unavailable, 0
