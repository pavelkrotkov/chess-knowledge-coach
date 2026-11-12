"""Revalidate an exact unfamiliar preview with read-only source guards."""

import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

from .fact_fingerprint import canonical
from .opening_profile_index import INDEX_NAME
from .opening_study_source import fingerprint, pin_inputs
from .opening_unfamiliar_legacy import resolve
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

        budget.check()
        first = resolve(db, root, learner, selection, version, directory, deadline=budget.expires)
        course = build(first, version)
        identity = first.get("_measurement_source") or first.get("measurement", {}).get(
            "source_identity"
        )
        before = pin_inputs(directory, root, files, before, identity)
        budget.check()
        second = resolve(db, root, learner, selection, version, directory, deadline=budget.expires)
        if first.get("_measurement_source") != second.get("_measurement_source") or canonical(
            build(second, version)
        ) != canonical(course):
            raise ValueError("opening preview changed")

        def check():
            budget.check()
            if fingerprint(files) != before:
                raise ValueError("opening source changed")

        check()
        yield course, budget, check
    finally:
        connection.close()
