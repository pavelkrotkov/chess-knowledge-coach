"""Bind one opening publication to current game and private sidecars."""

import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

from .fact_fingerprint import canonical
from .opening_queue_budget import study_budget
from .opening_revision_course import preview
from .opening_study_course import build
from .opening_study_source import fingerprint, inputs


@contextmanager
def admitted(
    database,
    directory,
    root,
    learner,
    game,
    position,
    move,
    version,
    *,
    browser=False,
    bounded=False,
):
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    try:
        db = SimpleNamespace(path=database, connection=connection)
        budget = study_budget(db, browser=browser)
        deadline = budget.expires if browser or bounded else None
        first = preview(
            db, root, learner, game, position, move, deadline=deadline, with_identity=True
        )
        budget.check()
        course = build(first, version, game, position, move)
        files = inputs(directory, first["_identity"], root)
        before = fingerprint(files)
        budget.check()
        second = preview(db, root, learner, game, position, move, deadline=deadline)
        budget.check()
        if canonical(build(second, version, game, position, move)) != canonical(course):
            raise ValueError("opening preview changed")

        def check():
            budget.check()
            if fingerprint(files) != before:
                raise ValueError("opening source changed")

        check()
        yield course, budget, check
    finally:
        connection.close()
