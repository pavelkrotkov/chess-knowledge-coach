"""Resolve a small number of current lesson sources for quick practice."""

from .coaching_practice_source import resolve_example
from .preview_snapshot import preview_history

EXAMPLE_LIMIT = 3


def choose(db, learner, group, check):
    lesson = group["lesson"]
    with preview_history(db, learner):
        for example in lesson["examples"][:EXAMPLE_LIMIT]:
            check()
            try:
                item = resolve_example(db, learner, lesson, example)
            except (ValueError, KeyError, TypeError, IndexError):
                continue
            check()
            if item:
                return item
    return None
