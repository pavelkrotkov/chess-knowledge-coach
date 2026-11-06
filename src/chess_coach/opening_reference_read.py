"""Read only precomputed reference matches for an owned opening decision."""

import json
import os
import sqlite3

from .opening_reference_index import INDEX_NAME
from .opening_reference_lookup import lookup as _matches
from .tactical_study_path import planning


def matches(root, subject, key):
    if root is None:
        return None
    try:
        directory, _ = planning(root, subject)
        path = directory / INDEX_NAME
        if path.is_symlink() or path.resolve(strict=True).parent != directory:
            return None
        info = path.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 20_000_000:
            return None
        return _matches(path, key)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error, json.JSONDecodeError):
        return None
