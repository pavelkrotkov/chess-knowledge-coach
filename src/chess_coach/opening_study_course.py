"""Adapt exactly one approved opening preview for the strict Study ledger."""

import re

from .course_preview import preview_hash
from .opening_recommendation_roles import LEGACY_SCHEMA as RECOMMENDATION_SCHEMA
from .opening_recommendation_roles import VERSION as RECOMMENDATION_VERSION
from .opening_recommendation_roles import checked_explanation
from .opening_revision_course import VERSION
from .opening_revision_roles import VERSION as DIRECT_VERSION
from .opening_revision_roles import explanation
from .opening_study_content import roles


def build(current, expected, game_id, position_id, move):
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or current["version"] != expected:
        raise ValueError("opening preview version differs")
    if (
        current["schema"]
        not in {VERSION, RECOMMENDATION_SCHEMA, DIRECT_VERSION, RECOMMENDATION_VERSION}
        or current["public_status"] != "available"
    ):
        raise ValueError("complete opening preview required")
    if current["schema"] == DIRECT_VERSION:
        expected_chapter = explanation(
            current["decision"], current["choice"], current["experiment"]
        )
    elif current["schema"] == RECOMMENDATION_VERSION:
        expected_chapter = checked_explanation(current)
    else:
        expected_chapter = None
    body = {
        "kind": "opening-study-course-v2" if expected_chapter else "opening-study-course-v1",
        "preview_version": expected,
        "selection": [game_id, position_id, move],
        "chapters": roles(current, expected_chapter),
    }
    return {"course": body, "course_sha256": preview_hash(body)}
