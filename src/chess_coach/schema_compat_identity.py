"""Bind schema compatibility to one private, exact service release and DB."""

import os
from pathlib import Path

from .opening_queue_files import read
from .tactical_study_path import planning
from .web_release import release_info

SLOT = "schema-32-compat.json"
VERSION = "schema-32-compat-v1"


def configured(path):
    mode = os.environ.get("CHESS_SCHEMA_COMPAT")
    if mode is None:
        return False
    if mode != "32":
        raise ValueError("unsupported schema compatibility mode")
    return Path(path).resolve(strict=True) == Path(os.environ["CHESS_DB"]).resolve(strict=True)


def _context(path):
    root = Path(os.environ["CHESS_PROJECT_ROOT"]).resolve(strict=True)
    data = (root / ".runtime" / "data").resolve(strict=True)
    database = Path(path).resolve(strict=True)
    if not data.is_relative_to(root) or not database.is_relative_to(data):
        raise ValueError("compatibility database is outside the project")
    directory, _ = planning(root, os.environ["CHESS_SUBJECT"])
    release = release_info()
    if release is None:
        raise ValueError("compatibility requires a sealed release")
    release_root = root / ".runtime" / "releases" / release["commit"]
    if not Path(release["module_path"]).is_relative_to(release_root):
        raise ValueError("compatibility release is outside the project")
    # Supported legacy writers retain inline values; inode and cookie bind that attestation.
    info = database.stat()
    return directory, {
        "database": [str(database), info.st_dev, info.st_ino],
        "release": release["commit"],
    }


def same_database(connection, path):
    main = next(row[2] for row in connection.execute("PRAGMA database_list") if row[1] == "main")
    if not main or not os.path.samefile(main, path):
        raise ValueError("compatibility connection differs from the selected database")


def verify(connection, path):
    if not configured(path):
        raise ValueError("schema compatibility is not selected")
    same_database(connection, path)
    directory, identity = _context(path)
    expected = read(directory / SLOT)
    cookie = connection.execute("PRAGMA schema_version").fetchone()[0]
    if expected != {"version": VERSION, **identity, "schema": cookie}:
        raise ValueError("legacy compatibility attestation unavailable")
    if connection.execute("PRAGMA user_version").fetchone()[0] != 32:
        raise ValueError("schema compatibility requires version 32")
