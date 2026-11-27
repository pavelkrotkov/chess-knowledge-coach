"""Rebind only fork sources when reading a mixed prepared course."""

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from .opening_queue_location import scope
from .schema_compat import readonly
from .tactical_course_budget import Budget
from .tactical_export_chapters import verify
from .tactical_export_contract import validate
from .tactical_export_groups import groups
from .tactical_export_selection import context
from .tactical_export_sources import lesson
from .tactical_study_preview import preview


def current(root, database, subject, corpus, envelope, version):
    saved = preview(envelope, version)
    body = validate(saved, corpus)
    path = Path(database).resolve(strict=True)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
    try:
        connection.row_factory = sqlite3.Row
        readonly(connection, path)
        connection.execute("PRAGMA query_only=ON")
        db = SimpleNamespace(connection=connection, path=path, capture_root=None)
        db.capture_root = scope(db, root)
        _forks(db, subject, corpus, body, Budget(db), version)
    finally:
        connection.close()


def _forks(db, subject, corpus, body, budget, artifact):
    pairs, modern, gaps, thematic, _ = context(body, corpus, budget)
    for pattern, group, roles, named in groups(body, gaps, modern=modern):
        pair = (pattern["skill"], pattern["operation"])
        if (pair == ("fork", "execute")) != (pattern["kind"] == "fork"):
            raise ValueError("fork pattern identity differs")
        if pattern["kind"] == "fork":
            current = lesson(db, subject, pattern, budget, pairs=pairs)
            verify(
                db,
                subject,
                corpus,
                pattern,
                current,
                group,
                budget,
                modern=modern,
                thematic=thematic,
                named=named,
                roles=roles,
                artifact=artifact,
            )
    budget.check()
