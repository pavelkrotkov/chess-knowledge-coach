"""Recheck every saved supporting observation and independent game."""

from .coaching_practice_source import resolve_example
from .lesson_cues import cues
from .tactical_export_binding import example
from .tactical_export_pattern import supports, versions


def lesson(db, subject, pattern, budget):
    saved = supports(pattern)
    items = [example(db, subject, pattern, binding, budget) for binding in saved]
    version = versions(pattern, items)
    question, habit, _ = cues(pattern["family"], pattern["operation"])
    return {
        "skill": pattern["skill"],
        "operation": pattern["operation"],
        "family": pattern["family"],
        "source_version": version,
        "examples": items,
        "question": question,
        "habit": habit,
    }


def choice(db, subject, lesson, budget):
    for item in lesson["examples"]:
        try:
            with budget.scope(snapshot=True):
                result = resolve_example(db, subject, lesson, item)
        except (ValueError, KeyError, TypeError, IndexError):
            continue
        if result:
            return result
    raise ValueError("owned practice source unavailable")
