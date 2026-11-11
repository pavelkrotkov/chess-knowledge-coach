"""Freeze one exact, bounded opening course before creating a Study."""

import os
import stat

from .fact_fingerprint import canonical
from .opening_study_source import fingerprint
from .tactical_course_publish import publish
from .tactical_export_input import MAX_BYTES, _read


def _stamp(path, course):
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o777 != 0o400
    ):
        raise ValueError("frozen opening course must be private and read-only")
    if canonical(_read(path)) != canonical(course):
        raise ValueError("opening course differs from frozen version")
    return fingerprint([path])


def freeze(path, course, budget, check):
    if len(canonical(course).encode()) > MAX_BYTES:
        raise ValueError("opening course exceeds limit")
    check()
    if path.exists() or path.is_symlink():
        if canonical(_read(path)) != canonical(course):
            raise ValueError("opening course differs from frozen version")
    else:
        publish(path, course, budget, readonly=True)
    expected = _stamp(path, course)

    def guarded():
        check()
        if fingerprint([path]) != expected:
            raise ValueError("frozen opening course changed")

    guarded()
    return guarded
