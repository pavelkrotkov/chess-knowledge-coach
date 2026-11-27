"""Rebuild one source-qualified ranked opening chapter for Study."""

from .course_preview import preview_hash
from .fact_fingerprint import canonical
from .opening_ranked_course import build_from_context
from .opening_study_chapter import chapter, line
from .study_inventory import named

KIND = "ranked-opening-study-v1"


def build(current, expected, context):
    if current["version"] != expected or canonical(current) != canonical(
        build_from_context(context)
    ):
        raise ValueError("opening preview version differs")
    chapters = current["chapters"]
    if len(chapters) != 1:
        raise ValueError("ranked opening chapter unavailable")
    value = chapters[0]
    snapshot = value["source_snapshot"]
    color = current["selection"]["color"]
    if value["mode"] != "conceal" or value["orientation"] != color:
        raise ValueError("ranked opening chapter differs")
    _, game = chapter(value, color, snapshot["prompt_fen"])
    if len(snapshot["lines"]) != 1 or not line(game, snapshot["lines"][0]):
        raise ValueError("ranked opening continuation differs")
    named(value, {"marker": "Chess coaching " + "0" * 16}, 0)
    body = {"kind": KIND, "preview_version": expected, "chapters": chapters}
    return {"course": body, "course_sha256": preview_hash(body)}
