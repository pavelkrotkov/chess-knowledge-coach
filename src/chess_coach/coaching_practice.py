"""Choose current practice examples for a coaching preview."""

from .coaching_practice_source import resolve_example
from .coaching_rehearsal import rehearsed_sources
from .recurrence_snapshot import read_snapshot


def choices(db, subject, preview, *, adaptive=False):
    with read_snapshot(db):
        keys = {
            str(example["evidence_id"])
            for group in preview["groups"]
            if adaptive and group["lesson"]["skill"] == "mate_in_one"
            for example in group["lesson"]["examples"]
        }
        rehearsed = rehearsed_sources(db, subject, keys)
        return [
            _choice(db, subject, group["lesson"], rehearsed, adaptive)
            for group in preview["groups"]
        ]


def _choice(db, subject, lesson, rehearsed, adaptive):
    examples = lesson["examples"]
    if adaptive and lesson["skill"] == "mate_in_one":
        examples = sorted(examples, key=lambda example: _rank(example, rehearsed))
    result = next(_available(db, subject, lesson, examples), None)
    if result and adaptive and result["kind"] == "mate":
        result["rehearsed"] = result["key"] in rehearsed
    return result


def _available(db, subject, lesson, examples):
    for example in examples:
        try:
            result = resolve_example(db, subject, lesson, example)
        except (ValueError, KeyError, TypeError, IndexError):
            continue
        if result:
            yield result


def _rank(example, rehearsed):
    key = str(example["evidence_id"])
    board = " ".join(example["fen"].split()[:4])
    return key in rehearsed, board in rehearsed.values()
