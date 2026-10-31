"""Recheck a frozen course against a read-only source database."""

import os
import sqlite3
from types import SimpleNamespace

from .course_preview import build
from .study_remote import StudyError


def revalidate(path, preview, frozen):
    current = build_readonly(path, preview)
    if current != frozen:
        raise StudyError("course sources changed; create and review a new preview")


def build_readonly(path, preview):
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return build(
            SimpleNamespace(connection=connection),
            os.environ["CHESS_SUBJECT"],
            os.environ["CHESS_CORPUS"],
            preview,
        )
    finally:
        connection.close()
