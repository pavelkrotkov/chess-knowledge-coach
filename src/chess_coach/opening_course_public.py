"""Access the owner-only pinned public index without importing or writing."""

import json
import sqlite3

from .opening_course_public_lookup import lookup
from .opening_profile_index import INDEX_NAME
from .opening_profile_read import _private_file
from .tactical_study_path import planning


def _identity(path):
    info = path.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def continuation(root, subject, parent, move, owned, *, expires=None):
    try:
        directory, _ = planning(root, subject)
        path = directory / INDEX_NAME
        if not _private_file(path, directory):
            raise ValueError("public index unavailable")
        before = _identity(path)
        result = lookup(path, parent, move, owned, expires=expires)
        if not _private_file(path, directory) or _identity(path) != before:
            raise ValueError("public index changed")
        return result, "available" if result else "no distinct continuation"
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        sqlite3.Error,
        json.JSONDecodeError,
    ):
        return None, "public index unavailable"
