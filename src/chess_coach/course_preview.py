"""Freeze source-admitted coaching and unfamiliar practice into a legal course."""

import hashlib
import json

from .coaching_practice import choices
from .course_evidence import revalidate_group
from .course_pgn import chapter
from .course_related import related
from .recurrence_snapshot import read_snapshot
from .unified_sources import resolve_source


def preview_hash(preview):
    encoded = json.dumps(preview, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def build(db, subject, corpus, envelope):
    preview = envelope["preview"]
    if envelope.get("preview_sha256") != preview_hash(preview):
        raise ValueError("coaching preview integrity check failed")
    if (preview.get("kind"), len(preview["groups"])) != ("coaching-preview-v1", 3):
        raise ValueError("three coaching lessons are required")
    with read_snapshot(db):
        selected = choices(db, subject, preview)
        if any(item is None for item in selected):
            raise ValueError("a coaching practice source is unavailable")
        by_kind = {item["kind"]: item for item in selected}
        if set(by_kind) != {"capture", "protection", "mate"}:
            raise ValueError("required coaching patterns are unavailable")
        chapters = [
            _personal(db, subject, group, item, revalidate_group(db, subject, group))
            for group, item in zip(preview["groups"], selected, strict=True)
        ]
        chapters.append(related(db, subject, corpus, by_kind["capture"], "capture"))
        chapters.append(related(db, subject, corpus, by_kind["mate"], "mate"))
    course = {"preview_sha256": envelope["preview_sha256"], "chapters": chapters}
    return {"course": course, "course_sha256": preview_hash(course)}


def _personal(db, subject, group, choice, games):
    lesson = group["lesson"]
    snapshot = resolve_source(db, "own-game", choice["version"], choice["key"], subject=subject)
    titles = {
        "capture": "Finding material gains",
        "protection": "Protecting your pieces",
        "mate": "Finding checkmate",
    }
    note = (
        f"From one of your games. This pattern appeared in {games} independent games. "
        f"{lesson['question']} {lesson['habit']}"
    )
    if choice["kind"] == "protection":
        note += " Replay this recorded line; it is not a proof that every alternative fails."
    return chapter(titles[choice["kind"]], note, snapshot, {"type": "own-game", **choice})
