"""Recheck an exact frozen opening Study when its send time is unknown."""

from .course_preview import preview_hash
from .mastery_time import parse_utc
from .opening_study_freeze import _stamp
from .opening_study_receipt import verified
from .tactical_export_input import _read
from .tactical_exposure_historical_positions import positions


def _course(directory, version, state):
    path = directory / f"opening-study-{version}-course.json"
    if not path.exists():
        return None
    course = _read(path)
    _stamp(path, course)
    body = course["course"]
    if body.get("preview_version") != version or course.get("course_sha256") != preview_hash(body):
        raise ValueError("opening Study exposure unavailable")
    if state.get("course_sha256") != course["course_sha256"]:
        raise ValueError("opening Study exposure unavailable")
    return course


def historical(directory, subject, version, state, target, cutoff):
    course = _course(directory, version, state)
    if course is None:
        return "legacy_coverage_unknown"
    found = positions(course["course"], state)
    if found is None:
        return "coverage_unavailable"
    if target not in found:
        return "not_recorded"
    if not verified(directory, subject, version, course):
        return "publication_time_unknown"
    # A later acknowledgement does not establish when an earlier send arrived.
    when = parse_utc(state.get("verified_at"))
    return "provided" if when is not None and when <= cutoff else "publication_time_unknown"
