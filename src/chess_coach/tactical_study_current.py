"""Revalidate a selected tactical export before any Study intent."""

import os
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

from .fact_fingerprint import canonical
from .opening_queue_location import scope
from .schema_compat import readonly
from .tactical_course import (
    DEFAULT_FORK_VERSION,
    DEFAULT_ROLES_VERSION,
    FORK_VERSIONS,
    NAMED_VERSION,
    SELECTED_ROLES_VERSION,
    SELECTED_VERSION,
    THEMATIC_SELECTED_VERSION,
    THEMATIC_VERSION,
)
from .tactical_course_budget import Budget
from .tactical_course_choice import SLICE_SECONDS as SELECTED_SECONDS
from .tactical_export import build
from .tactical_study_preview import preview


@contextmanager
def revalidate(
    path, envelope, expected, *, with_budget=False, project_root=None, subject=None, corpus=None
):
    saved_preview = preview(envelope, expected)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
    connection.row_factory = sqlite3.Row
    readonly(connection, path)
    connection.execute("PRAGMA query_only=ON")
    try:
        db = SimpleNamespace(connection=connection, path=path, capture_root=None)
        db.capture_root = scope(db, project_root)
        budget = Budget(
            db,
            slice_seconds=SELECTED_SECONDS
            if saved_preview["kind"]
            in {
                SELECTED_VERSION,
                THEMATIC_SELECTED_VERSION,
                NAMED_VERSION,
                SELECTED_ROLES_VERSION,
                *FORK_VERSIONS,
            }
            else None,
        )
        options = (
            {"artifact": expected}
            if saved_preview["kind"]
            in {
                THEMATIC_VERSION,
                THEMATIC_SELECTED_VERSION,
                NAMED_VERSION,
                DEFAULT_ROLES_VERSION,
                DEFAULT_FORK_VERSION,
                SELECTED_ROLES_VERSION,
                *FORK_VERSIONS,
            }
            else {}
        )
        current = build(
            db,
            subject if subject is not None else os.environ["CHESS_SUBJECT"],
            corpus if corpus is not None else os.environ["CHESS_CORPUS"],
            saved_preview,
            budget,
            **options,
        )
        if canonical(current) != canonical(envelope):
            raise ValueError("tactical export changed")
        budget.check()
        yield budget if with_budget else budget.check
    finally:
        connection.close()
