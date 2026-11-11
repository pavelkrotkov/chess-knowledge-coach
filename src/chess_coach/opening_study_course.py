"""Adapt exactly one approved opening preview for the strict Study ledger."""

import re

from .course_preview import preview_hash
from .opening_revision_course import VERSION
from .opening_study_chapter import chapter, line


def _content(current):
    chapters = current["chapters"]
    if [item["kind"] for item in chapters] != ["owned", "public"]:
        raise ValueError("complete opening preview required")
    decision = current["decision"]
    color, fen = decision["color"], decision["fen"]
    owned, game = chapter(chapters[0], color, fen)
    public, reference = chapter(chapters[1], color, fen, exact=False)
    experiment = current["experiment"]
    if len(game.variations) != 2 or not all(
        line(game, experiment[branch]["uci"]) for branch in ("played", "alternative")
    ):
        raise ValueError("opening variations differ")
    if not all(
        str(chapters[1][key]) in reference.comment for key in ("source", "license", "license_url")
    ):
        raise ValueError("public attribution differs")
    return [owned, public]


def build(current, expected, game_id, position_id, move):
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or current["version"] != expected:
        raise ValueError("opening preview version differs")
    if current["schema"] != VERSION or current["public_status"] != "available":
        raise ValueError("complete opening preview required")
    body = {
        "kind": "opening-study-course-v1",
        "preview_version": expected,
        "selection": [game_id, position_id, move],
        "chapters": _content(current),
    }
    return {"course": body, "course_sha256": preview_hash(body)}
