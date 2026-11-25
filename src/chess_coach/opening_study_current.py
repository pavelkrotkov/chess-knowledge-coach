"""Bind one opening publication to current game and private sidecars."""

import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

from .fact_fingerprint import canonical
from .opening_queue_budget import study_budget
from .opening_study_course import build
from .opening_study_revision import current, watched
from .opening_study_source import fingerprint
from .schema_compat import readonly


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
    readonly(connection, database)
    connection.execute("PRAGMA query_only=ON")
    try:
        db = SimpleNamespace(path=database, connection=connection)
        budget = study_budget(db, browser=browser)
        deadline = budget.expires if browser or bounded else None
        try:
            first = current(
                db,
                root,
                learner,
                game,
                position,
                move,
                version,
                deadline=deadline,
                with_identity=True,
            )
            budget.check()
            course = build(first, version, game, position, move)
            files, deadline = watched(first, directory, root, budget, deadline)
            before = fingerprint(files)
            budget.check()
            second = current(db, root, learner, game, position, move, version, deadline=deadline)
            budget.check()
            if canonical(build(second, version, game, position, move)) != canonical(course):
                raise ValueError("opening preview changed")
        except ValueError:
            budget.check()
            raise

        def check():
            budget.check()
            if fingerprint(files) != before:
                raise ValueError("opening source changed")

        check()
        yield course, budget, check
    finally:
        connection.close()
