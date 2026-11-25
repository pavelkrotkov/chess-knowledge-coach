"""Open the selected project database read-only for a private profile."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from .schema_compat import configured, readonly
from .tactical_study_path import planning
from .web_paths import inside


def open_database(root, *, database=None):
    root = Path(root).resolve(strict=True)
    data = (root / ".runtime" / "data").resolve(strict=True)
    if not data.is_relative_to(root):
        raise ValueError("project data unavailable")
    path = inside(data, os.environ["CHESS_DB"] if database is None else database, existing=True)
    if (
        database is not None
        and os.environ.get("CHESS_SCHEMA_COMPAT") is not None
        and not configured(path, selected=database)
    ):
        raise ValueError("selected compatibility database differs")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA temp_store=MEMORY")
        readonly(connection, path, selected=database)
        connection.execute("PRAGMA query_only=ON")
        return connection, path
    except BaseException:
        connection.close()
        raise


@contextmanager
def private_database(root, subject, *, database=None):
    planning(root, subject)
    connection, path = open_database(root, database=database)
    try:
        yield SimpleNamespace(connection=connection, path=path)
    finally:
        connection.close()
