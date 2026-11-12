"""Revalidate an exact unfamiliar preview with read-only source guards."""

import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

from .fact_fingerprint import canonical
from .opening_profile_index import INDEX_NAME
from .opening_study_source import fingerprint
from .opening_unfamiliar_course import preview
from .opening_unfamiliar_study_course import build
from .tactical_course_budget import Budget


@contextmanager
def admitted(database, directory, root, learner, version, selection=None):
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    try:
        db = SimpleNamespace(path=database, connection=connection)
        budget = Budget(db)
        config = root / ".runtime" / "config.env"
        files = [directory / INDEX_NAME, config, config.resolve()]
        before = fingerprint(files)

        def current():
            return (
                preview(db, root, learner, selection) if selection else preview(db, root, learner)
            )

        course = build(current(), version)
        if canonical(build(current(), version)) != canonical(course):
            raise ValueError("opening preview changed")

        def check():
            budget.check()
            if fingerprint(files) != before:
                raise ValueError("opening source changed")

        check()
        yield course, budget, check
    finally:
        connection.close()
