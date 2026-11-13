"""Recheck owned lessons and build ungraded, source-linked chapters."""

from .coaching_practice_source import available, resolve_example
from .course_guidance import objective
from .course_pgn import chapter
from .recurrence_snapshot import read_snapshot
from .tactical_course_evidence import independent
from .unified_sources import resolve_source


def owned(db, subject, group, *, bindings=None):
    if bindings is None:
        bindings = independent(db, subject, group)
    with read_snapshot(db):
        snapshots = []
        lesson = group["lesson"]
        choice = next(
            available(db, subject, lesson, lesson["examples"], resolve_example, snapshots), None
        )
        if choice is None or choice["kind"] not in {
            "capture",
            "protection",
            "mate",
            "short_mate",
            "fork",
        }:
            return None
        return (
            choice,
            owned_chapter(db, subject, group, choice, bindings, snapshot=snapshots[0]),
            bindings,
        )


def owned_chapter(db, subject, group, choice, bindings, *, snapshot=None):
    count = len({item["game_key"] for item in bindings})
    if snapshot is None:
        snapshot = resolve_source(db, "own-game", choice["version"], choice["key"], subject=subject)
    lesson = group["lesson"]
    example = next(
        item for item in lesson["examples"] if item["evidence_id"] == choice["evidence_id"]
    )
    note = (
        f"Provisional recurring observation across {count} independent games. "
        f"Source review: {example['review']}. Played {example['played']}. "
        f"{' '.join(example['facts'])} {lesson['question']} {lesson['habit']} "
        "This is a recorded line, not a mastery result."
    )
    note, _ = objective(note, snapshot, choice["kind"])
    return chapter("Your recurring pattern", note, snapshot, {"type": "own-game", **choice})
