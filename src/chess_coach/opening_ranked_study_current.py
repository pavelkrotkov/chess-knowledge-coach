"""Admit a ranked Study from one current source observation."""

import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

from .opening_queue_budget import study_budget
from .opening_ranked_study_course import build
from .opening_ranked_study_guard import guard
from .opening_unfamiliar_course import preview
from .schema_compat import readonly


@contextmanager
def admitted(database, directory, root, learner, version, choice, *, browser=False):
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)
    connection.row_factory = sqlite3.Row
    readonly(connection, database)
    connection.execute("PRAGMA query_only=ON")
    try:
        db = SimpleNamespace(path=database, connection=connection)
        budget = study_budget(db, browser=browser)
        current, context = preview(
            db, root, learner, choice=choice, budget=budget, with_context=True
        )
        course = build(current, version, context)
        check = guard(context, db, root, learner, directory, version, course)
        check()
        yield course, budget, check
    finally:
        connection.close()
