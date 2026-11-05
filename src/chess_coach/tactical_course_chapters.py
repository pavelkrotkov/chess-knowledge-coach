"""Recheck owned lessons and build ungraded, source-linked chapters."""

from .coaching_practice import choices
from .course_guidance import objective
from .course_pgn import chapter
from .tactical_course_evidence import independent
from .unified_sources import resolve_source


def owned(db, subject, group):
    bindings = independent(db, subject, group)
    count = len({item["game_key"] for item in bindings})
    choice = choices(db, subject, {"groups": [group]})[0]
    if choice is None or choice["kind"] not in {"capture", "protection", "mate", "short_mate"}:
        return None
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
    result = chapter("Your recurring pattern", note, snapshot, {"type": "own-game", **choice})
    return choice, result, bindings


def challenge(choice):
    if choice["kind"] == "capture":
        return f"/decisions/{choice['position_id']}/related-captures"
    if choice["kind"] in {"mate", "short_mate"}:
        return f"/evidence/{choice['evidence_id']}/related-mates"
    return None
