"""Bind the new history index to the current verified immutable prefix."""

from .opening_course_public import _identity
from .opening_full_history_build import INDEX_NAME
from .opening_profile_read import _private_file
from .opening_recent_read import source
from .tactical_study_path import planning


def locate(root, subject):
    directory, _ = planning(root, subject)
    prefix, receipt = source(directory)
    path = directory / INDEX_NAME
    if not _private_file(path, directory) or path.stat().st_mode & 0o777 != 0o400:
        raise ValueError("full history reference unavailable")
    return path, _identity(path), _identity(prefix), receipt
