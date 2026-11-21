"""Open the selected project database read-only for a private profile."""

import os
import sqlite3
from pathlib import Path

from .schema_compat import readonly
from .web_paths import inside


def open_database(root):
    root = Path(root).resolve(strict=True)
    data = (root / ".runtime" / "data").resolve(strict=True)
    if not data.is_relative_to(root):
        raise ValueError("project data unavailable")
    path = inside(data, os.environ["CHESS_DB"], existing=True)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA temp_store=MEMORY")
        readonly(connection, path)
        connection.execute("PRAGMA query_only=ON")
        return connection, path
    except BaseException:
        connection.close()
        raise
