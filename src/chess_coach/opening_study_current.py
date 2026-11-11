"""Bind one opening publication to current game and private sidecars."""

import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

from .fact_fingerprint import canonical
from .opening_experiment_current import current as experiment
from .opening_revision_course import preview
from .opening_study_course import build
from .opening_study_source import fingerprint, inputs
from .tactical_course_budget import Budget


@contextmanager
def admitted(database, directory, root, learner, game, position, move, version):
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    try:
        db = SimpleNamespace(path=database, connection=connection)
        budget = Budget(db)
        first = preview(db, root, learner, game, position, move)
        course = build(first, version, game, position, move)
        _, _, _, identity = experiment(db, root, learner, game, position, move, with_identity=True)
        files = inputs(directory, identity, root)
        before = fingerprint(files)
        second = preview(db, root, learner, game, position, move)
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
