"""Reconstruct a complete, source-qualified ranked lesson for private Study."""

from .course_preview import preview_hash
from .fact_fingerprint import canonical
from .opening_ranked_study_course import validate_chapter
from .opening_ranked_teaching import assemble

KIND = "ranked-opening-teaching-study-v1"


def build(current, expected, context, qualification):
    if current["version"] != expected or canonical(current) != canonical(
        assemble(context, qualification)
    ):
        raise ValueError("opening preview version differs")
    chapters = current["chapters"]
    if current["public_status"] != "available" or [value["kind"] for value in chapters] != [
        "explanation",
        "example",
        "practice",
    ]:
        raise ValueError("complete opening lesson unavailable")
    if chapters[1]["source"]["record"] == chapters[2]["source"]["record"]:
        raise ValueError("distinct public rehearsal unavailable")
    for index, value in enumerate(chapters):
        validate_chapter(value, current["selection"]["color"], index)
    body = {"kind": KIND, "preview_version": expected, "chapters": chapters}
    return {"course": body, "course_sha256": preview_hash(body)}
