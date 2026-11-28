"""Render or download one exact part of a privately offered tactical course."""

from flask import abort, request

from .course_parts import partition
from .tactical_course_display import chapter as display
from .tactical_course_presentation import lines as presentation_lines
from .tactical_export_groups import course_groups


def _index(name, count, default=0):
    value = request.args.get(name, str(default))
    if not value.isascii() or not value.isdecimal() or len(value) > 4:
        abort(400)
    index = int(value)
    if index >= count:
        abort(400)
    return index


def selected(course, artifact):
    manifest = partition(course_groups(course), artifact)
    return manifest, manifest["parts"][_index("part", manifest["part_count"])]


def shown(course, part):
    index = _index("chapter", len(course["chapters"]), part["indices"][0])
    if index not in part["indices"]:
        abort(400, "Chapter is outside the selected part.")
    chapter = course["chapters"][index]
    result = display(chapter, index, _index("line", len(presentation_lines(chapter))))
    source = result["chapter"]["source"]
    result["evidence"] = source.get("evidence_id") or source.get("binding", {}).get("evidence_id")
    return result
