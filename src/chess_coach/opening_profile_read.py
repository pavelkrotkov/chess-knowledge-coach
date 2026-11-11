"""Read the private project-local ordered public reference index."""

import json
import os
import sqlite3
import stat

from .opening_profile_index import INDEX_NAME
from .opening_profile_lookup import lookup
from .tactical_study_path import planning


def profile(root, subject, parent, move, *, expires=None):
    if root is None:
        return None
    try:
        directory, _ = planning(root, subject)
        path = directory / INDEX_NAME
        if not _private_file(path, directory):
            return None
        return lookup(path, parent, move, expires=expires)
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        sqlite3.Error,
        json.JSONDecodeError,
    ):
        return None


def _private_file(path, directory):
    if path.is_symlink() or path.resolve(strict=True).parent != directory:
        return False
    info = path.stat()
    return (
        stat.S_ISREG(info.st_mode)
        and info.st_uid == os.getuid()
        and not info.st_mode & 0o077
        and info.st_size <= 20_000_000
    )
