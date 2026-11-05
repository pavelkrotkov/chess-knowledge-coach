"""Revalidate a selected tactical export before any Study intent."""

import os
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

from .fact_fingerprint import canonical
from .tactical_course_budget import Budget
from .tactical_export import build
from .tactical_study_preview import preview


@contextmanager
def revalidate(path, envelope, expected):
    saved_preview = preview(envelope, expected)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    try:
        db = SimpleNamespace(connection=connection)
        budget = Budget(db)
        current = build(
            db, os.environ["CHESS_SUBJECT"], os.environ["CHESS_CORPUS"], saved_preview, budget
        )
        if canonical(current) != canonical(envelope):
            raise ValueError("tactical export changed")
        budget.check()
        yield budget.check
    finally:
        connection.close()
