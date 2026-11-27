"""Resolve a small number of current lesson sources for quick practice."""

from contextlib import nullcontext

from .coaching_practice_source import resolve_example
from .preview_snapshot import preview_history

EXAMPLE_LIMIT = 3


def choose(db, learner, group, check, *, source_check=False, _history=None):
    lesson = group["lesson"]
    with preview_history(db, learner) if _history is None else nullcontext(_history) as history:
        examples = lesson["examples"][:EXAMPLE_LIMIT]
        options = {}
        if source_check:
            if _history is None:
                history.targets(example["position_id"] for example in examples)
            options = {"check": check, "_history": history}
        for example in examples:
            check()
            try:
                item = resolve_example(db, learner, lesson, example, **options)
            except (ValueError, KeyError, TypeError, IndexError):
                continue
            check()
            if item:
                return item
    return None
