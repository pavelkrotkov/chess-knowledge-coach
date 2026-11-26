"""Recheck a frozen course against a read-only source database."""

import os
import sqlite3
from types import SimpleNamespace

from .course_preview import build
from .opening_queue_location import scope
from .schema_compat import readonly
from .study_remote import StudyError


def revalidate(path, preview, frozen, *, project_root=None):
    current = build_readonly(path, preview, project_root=project_root)
    if current != frozen:
        raise StudyError("course sources changed; create and review a new preview")


def build_readonly(path, preview, *, project_root=None):
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    readonly(connection, path)
    try:
        db = SimpleNamespace(connection=connection, path=path, capture_root=None)
        db.capture_root = scope(db, project_root)
        return build(
            db,
            os.environ["CHESS_SUBJECT"],
            os.environ["CHESS_CORPUS"],
            preview,
        )
    finally:
        connection.close()
