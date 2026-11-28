"""Validate complete saved-course grouping, coverage, and chapter order."""

from .tactical_export_coverage import selected as covered
from .tactical_export_gaps import OWN_REASONS, selected
from .tactical_export_grouping import chapters


def groups(body, gaps, *, modern):
    index, seen = 0, set()
    for pattern in body["patterns"]:
        pair = (pattern["skill"], pattern["operation"])
        if pair in seen:
            raise ValueError("duplicate tactical pattern")
        seen.add(pair)
        group, index, roles, named = chapters(body["chapters"], index, pattern, body["kind"])
        covered(pattern, body["selection"]["coverage"])
        selected(pattern, group, gaps, modern=modern, roles=roles)
        yield pattern, group, roles, named
    if any(reason not in OWN_REASONS and pair not in seen for pair, reason in gaps.items()):
        raise ValueError("related omission has no selected pattern")
    if index != len(body["chapters"]):
        raise ValueError("unexpected chapter order")


def course_groups(course):
    kind = course["kind"].replace("-export-v", "-v")
    result, index = [], 0
    for pattern in course["patterns"]:
        group, index, _, _ = chapters(course["chapters"], index, pattern, kind)
        result.append(group)
    if index != len(course["chapters"]):
        raise ValueError("course chapter order differs")
    return result
