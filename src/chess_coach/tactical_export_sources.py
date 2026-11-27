"""Recheck every saved supporting observation and independent game."""

from .coaching_practice_source import resolve_example
from .lesson_cues import cues
from .tactical_course_chapters import owned_chapter
from .tactical_course_presentation import VERSION as FORK_PRESENTATION
from .tactical_course_selection import PAIRS
from .tactical_export_binding import example
from .tactical_export_compare import compare
from .tactical_export_pattern import supports, versions


def lesson(db, subject, pattern, budget, *, pairs=PAIRS):
    saved = supports(pattern, pairs=pairs)
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


def verify_owned(db, subject, pattern, lesson, chapters, budget, selected, roles):
    owned_saved = chapters[1] if roles else chapters[0]
    with budget.scope(snapshot=True):
        owned = owned_chapter(
            db,
            subject,
            {"lesson": lesson},
            selected,
            pattern["supporting_sources"],
            illustrated=owned_saved.get("presentation", {}).get("version") == FORK_PRESENTATION,
        )
    with budget.scope(snapshot=False):
        if roles:
            if pattern["kind"] == "protection":
                from .tactical_course_protection_roles import explanation
            elif pattern["kind"] == "fork":
                from .tactical_course_fork_roles import explanation
            else:
                from .tactical_course_capture_roles import explanation

            compare(chapters[0], explanation(owned))
            owned = {**owned, "role": "worked"}
        compare(owned_saved, owned)
