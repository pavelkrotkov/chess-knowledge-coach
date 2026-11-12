"""Admit exact unfamiliar-opening chapters to the strict Study ledger."""

import re

from .course_preview import preview_hash
from .fact_fingerprint import canonical, digest
from .opening_unfamiliar_course import SELECTED_VERSION, VERSION
from .opening_unfamiliar_selected_validate import validate_content
from .opening_unfamiliar_study_lesson import lesson
from .study_inventory import named

KIND = "unfamiliar-opening-study-v1"


def _version(current, expected):
    payload = {"schema": VERSION, "report": current["report"], "chapters": current["chapters"]}
    if "selection" in current:
        payload.update(schema=SELECTED_VERSION, selection=current["selection"])
        validate_content(current)
    if any(
        (
            not re.fullmatch(r"[0-9a-f]{64}", expected),
            current["version"] != expected,
            digest(canonical(payload)) != expected,
        )
    ):
        raise ValueError("opening preview version differs")


def _chapters(report, values):
    colors = [color for color in ("white", "black") if report[color]]
    if not colors or [value["orientation"] for value in values] != colors:
        raise ValueError("unfamiliar opening lessons unavailable")
    return [lesson(report, color, value) for color, value in zip(colors, values, strict=True)]


def build(current, expected):
    _version(current, expected)
    chapters = _chapters(current["report"], current["chapters"])
    for index, item in enumerate(chapters):
        named(item, {"marker": "Chess coaching " + "0" * 16}, index)
    body = {"kind": KIND, "preview_version": expected, "chapters": chapters}
    return {"course": body, "course_sha256": preview_hash(body)}
