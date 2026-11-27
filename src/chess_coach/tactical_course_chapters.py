"""Recheck owned lessons and build ungraded, source-linked chapters."""

from functools import partial

from .coaching_practice_source import available, resolve_example
from .course_guidance import objective
from .course_pgn import chapter
from .recurrence_snapshot import read_snapshot
from .tactical_course_evidence import independent
from .tactical_course_fork_chapter import build as fork_chapter
from .unified_sources import resolve_source


def owned(db, subject, group, *, bindings=None, identity_for=None):
    if bindings is None:
        bindings = independent(db, subject, group)
    with read_snapshot(db):
        snapshots = []
        lesson = group["lesson"]
        resolver = partial(resolve_example, identity_for=identity_for)
        choice = next(available(db, subject, lesson, lesson["examples"], resolver, snapshots), None)
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
            owned_chapter(
                db, subject, group, choice, bindings, snapshot=snapshots[0], illustrated=True
            ),
            bindings,
        )


def owned_chapter(db, subject, group, choice, bindings, *, snapshot=None, illustrated=False):
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
    source = {"type": "own-game", **choice}
    if snapshot["objective"] == "protect_threatened_piece":
        from .tactical_course_protection_roles import worked

        return worked(note, snapshot, source)
    note, _ = objective(note, snapshot, choice["kind"])
    if illustrated and choice["kind"] == "fork":
        return fork_chapter(note, snapshot, source)
    return chapter("Your recurring pattern", note, snapshot, source)
