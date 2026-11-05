"""Validate the bounded independent supporting pattern metadata."""

from .tactical_course_selection import PAIRS, PER_PAIR


def _independent(pattern, saved):
    if len({entry["game_key"] for entry in saved}) != len(saved):
        raise ValueError("supporting games are not independent")
    if type(pattern["independent_games"]) is not int or pattern["independent_games"] != len(saved):
        raise ValueError("supporting game count differs")


def supports(pattern):
    if (pattern["skill"], pattern["operation"]) not in PAIRS:
        raise ValueError("unsupported pattern")
    saved = pattern["supporting_sources"]
    if not isinstance(saved, list) or not 2 <= len(saved) <= 3:
        raise ValueError("unsupported source count")
    if (
        type(pattern["inspected_misses"]) is not int
        or not len(saved) <= pattern["inspected_misses"] <= PER_PAIR
    ):
        raise ValueError("invalid observed sample count")
    _independent(pattern, saved)
    return saved


def versions(pattern, items):
    if pattern["review_states"] != [item["review"] for item in items]:
        raise ValueError("supporting reviews differ")
    versions = {item["detector_version"] for item in items}
    if len(versions) != 1:
        raise ValueError("supporting detector versions differ")
    return versions.pop()
