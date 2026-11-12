"""Recognize a retained exact unmeasured Study intent."""

from .opening_queue_files import read
from .opening_unfamiliar_course import preview
from .opening_unfamiliar_study_course import build
from .tactical_study_ledger import validate


def retained(directory, course):
    try:
        version = course["version"]
        state = read(directory / f"opening-study-{version}-intent.json")
        if not isinstance(state, dict):
            return False
        body = build(course, version)
        validate(state, body["course"]["chapters"])
        return state.get("course_sha256") == body["course_sha256"]
    except Exception:
        return False


def resolve(db, root, learner, selection, version, directory):
    value = preview(db, root, learner, selection) if selection else preview(db, root, learner)
    if selection and value["version"] != version and value.get("legacy_version") == version:
        value = preview(db, root, learner, selection, legacy=True)
        if not retained(directory, value):
            raise ValueError("previous opening intent unavailable")
    return value
