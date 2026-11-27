"""Resolve a small number of current lesson sources for quick practice."""

from .coaching_practice_source import resolve_example
from .preview_snapshot import preview_history

EXAMPLE_LIMIT = 3


def choose(db, learner, group, check, *, source_check=False):
    lesson = group["lesson"]
    with preview_history(db, learner) as history:
        examples = lesson["examples"][:EXAMPLE_LIMIT]
        if source_check:
            history.targets(example["position_id"] for example in examples)
        for example in examples:
            check()
            try:
                options = {"check": check, "_history": history} if source_check else {}
                item = resolve_example(db, learner, lesson, example, **options)
            except (ValueError, KeyError, TypeError, IndexError):
                continue
            check()
            if item:
                return item
    return None
