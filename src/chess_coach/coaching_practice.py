"""Choose current practice examples for a coaching preview."""

from .coaching_practice_source import available, resolve_example
from .coaching_rehearsal import keys as mate_keys
from .coaching_rehearsal import rehearsed_sources
from .coaching_short_rehearsal import rehearsed_sources as short_rehearsed_sources
from .coaching_short_selection import boards as short_boards
from .coaching_short_selection import keys as short_keys
from .coaching_short_selection import mark as mark_short
from .coaching_short_selection import order as order_short
from .recurrence_snapshot import read_snapshot


def choices(db, subject, preview, *, adaptive=False):
    with read_snapshot(db):
        rehearsed = rehearsed_sources(db, subject, mate_keys(preview, adaptive))
        short_rehearsed = short_rehearsed_sources(
            db, subject, short_keys(preview, adaptive), short_boards(preview, adaptive)
        )
        return [
            _choice(db, subject, group["lesson"], rehearsed, short_rehearsed, adaptive)
            for group in preview["groups"]
        ]


def _choice(db, subject, lesson, rehearsed, short_rehearsed, adaptive):
    examples = lesson["examples"]
    if adaptive and lesson["skill"] == "mate_in_one":
        examples = sorted(examples, key=lambda example: _rank(example, rehearsed))
    examples = order_short(lesson, examples, short_rehearsed, adaptive)
    result = next(available(db, subject, lesson, examples, resolve_example), None)
    if result and adaptive and result["kind"] == "mate":
        result["rehearsed"] = result["key"] in rehearsed
    mark_short(result, examples, short_rehearsed, adaptive)
    return result


def _rank(example, rehearsed):
    key = str(example["evidence_id"])
    board = " ".join(example["fen"].split()[:4])
    return key in rehearsed, board in rehearsed.values()
