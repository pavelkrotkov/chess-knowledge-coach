"""Rebind non-protection sources when reading a mixed prepared course."""

import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from .objective_protection_contract import VERSION as PROTECTION_VERSION
from .opening_queue_location import scope
from .schema_compat import readonly
from .tactical_course_budget import Budget
from .tactical_course_choice import SLICE_SECONDS as SELECTED_SECONDS
from .tactical_course_contract import MIXED_SELECTED_VERSION, SELECTED_MATE_VERSION
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
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as connection:
        connection.row_factory = sqlite3.Row
        readonly(connection, path)
        connection.execute("PRAGMA query_only=ON")
        db = SimpleNamespace(connection=connection, path=path, capture_root=None)
        db.capture_root = scope(db, root)
        slice_seconds = (
            SELECTED_SECONDS
            if body["kind"] in {MIXED_SELECTED_VERSION, SELECTED_MATE_VERSION}
            else None
        )
        _current_groups(db, subject, corpus, body, Budget(db, slice_seconds=slice_seconds), version)


def _current_groups(db, subject, corpus, body, budget, artifact):
    pairs, modern, gaps, thematic, _ = context(body, corpus, budget)
    for pattern, group, roles, named in groups(body, gaps, modern=modern):
        pair = (pattern["skill"], pattern["operation"])
        if (pair == ("hanging_piece", "prevent")) != (pattern["kind"] == "protection"):
            raise ValueError("protection pattern identity differs")
        if pattern["kind"] == "protection":
            source = group[1]["source"]
            if (source["version"], source["kind"], group[1]["source_snapshot"]["objective"]) != (
                PROTECTION_VERSION,
                "protection",
                "protect_threatened_piece",
            ):
                raise ValueError("protection chapter identity differs")
            continue
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
