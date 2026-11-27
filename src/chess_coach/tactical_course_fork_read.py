"""Rebind only fork sources when reading a mixed prepared course."""

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from .opening_queue_location import scope
from .schema_compat import readonly
from .tactical_course_budget import Budget
from .tactical_export_chapters import verify
from .tactical_export_contract import validate
from .tactical_export_coverage import selected as covered
from .tactical_export_gaps import OWN_REASONS, selected
from .tactical_export_grouping import chapters
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
    pairs, modern, gaps, thematic, kind = context(body, corpus, budget)
    index, seen = 0, set()
    for pattern in body["patterns"]:
        pair = (pattern["skill"], pattern["operation"])
        if pair in seen:
            raise ValueError("duplicate tactical pattern")
        seen.add(pair)
        group, index, roles, named = chapters(body["chapters"], index, pattern, kind)
        covered(pattern, body["selection"]["coverage"])
        selected(pattern, group, gaps, modern=modern, roles=roles)
        if pattern["kind"] == "fork":
            current = lesson(db, subject, pattern, budget, pairs=pairs)
            verify(
                db, subject, corpus, pattern, current, group, budget,
                modern=modern, thematic=thematic, named=named, roles=roles, artifact=artifact,
            )
    if any(reason not in OWN_REASONS and pair not in seen for pair, reason in gaps.items()):
        raise ValueError("related omission has no selected pattern")
    if index != len(body["chapters"]):
        raise ValueError("unexpected chapter order")
    budget.check()
