"""Retain one private, crash-safe publication intent."""

import json
import os
import secrets
from pathlib import Path

from .course_preview import preview_hash
from .study_remote import StudyError


def open_intent(path, course):
    if course.get("course_sha256") != preview_hash(course["course"]):
        raise StudyError("course integrity check failed")
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
        if state["course_sha256"] != course["course_sha256"]:
            raise StudyError("another course intent already exists")
        return state
    marker = "Chess coaching " + secrets.token_hex(8)
    state = {
        "course_sha256": course["course_sha256"],
        "marker": marker,
        "study": None,
        "create_pending": False,
        "empty_chapter": None,
        "chapters": ["new"] * len(course["course"]["chapters"]),
        "complete": False,
    }
    save(path, state)
    return state


def save(path, state):
    temp = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    descriptor = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(state, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    directory = os.open(Path(path).parent, os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
