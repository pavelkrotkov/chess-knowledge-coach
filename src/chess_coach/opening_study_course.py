"""Adapt exactly one approved opening preview for the strict Study ledger."""

import re

from .course_preview import preview_hash
from .opening_recommendation_preview import SCHEMA as RECOMMENDATION_SCHEMA
from .opening_revision_course import VERSION
from .opening_revision_roles import VERSION as DIRECT_VERSION
from .opening_revision_roles import explanation
from .opening_study_chapter import chapter
from .opening_study_content import content


def _content(current, direct):
    chapters = current["chapters"]
    roles = ["explanation", "owned", "public"] if direct else ["owned", "public"]
    if [item["kind"] for item in chapters] != roles:
        raise ValueError("complete opening preview required")
    decision = current["decision"]
    color, fen = decision["color"], decision["fen"]
    if direct and chapters[0] != explanation(decision, current["choice"], current["experiment"]):
        raise ValueError("opening explanation differs")
    prefix = [chapter(chapters[0], color, fen)[0]] if direct else []
    return prefix + content(current, chapters[-2:])


def build(current, expected, game_id, position_id, move):
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or current["version"] != expected:
        raise ValueError("opening preview version differs")
    if (
        current["schema"] not in {VERSION, RECOMMENDATION_SCHEMA, DIRECT_VERSION}
        or current["public_status"] != "available"
    ):
        raise ValueError("complete opening preview required")
    direct = current["schema"] == DIRECT_VERSION
    body = {
        "kind": "opening-study-course-v2" if direct else "opening-study-course-v1",
        "preview_version": expected,
        "selection": [game_id, position_id, move],
        "chapters": _content(current, direct),
    }
    return {"course": body, "course_sha256": preview_hash(body)}
