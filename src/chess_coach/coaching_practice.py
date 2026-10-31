"""Choose current practice examples for a coaching preview."""

from .coaching_practice_source import resolve_example
from .recurrence_snapshot import read_snapshot


def choices(db, subject, preview):
    with read_snapshot(db):
        return [_choice(db, subject, group["lesson"]) for group in preview["groups"]]


def _choice(db, subject, lesson):
    for example in lesson["examples"]:
        try:
            result = resolve_example(db, subject, lesson, example)
            if result:
                return result
        except (ValueError, KeyError, TypeError, IndexError):
            continue
    return None
