"""Revalidate a selected tactical export before any Study intent."""

import os
import re
import sqlite3
from types import SimpleNamespace

from .course_preview import preview_hash
from .fact_fingerprint import canonical
from .tactical_course import VERSION as PREVIEW_VERSION
from .tactical_course_budget import Budget
from .tactical_export import VERSION, build


def _preview(envelope, expected):
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or envelope.get("kind") != VERSION:
        raise ValueError("unsupported tactical export")
    body = envelope["export"]
    if envelope.get("export_sha256") != expected or preview_hash(body) != expected:
        raise ValueError("tactical export hash differs")
    preview = {
        "kind": PREVIEW_VERSION,
        "policy": "provisional-recurring-tactics-v1",
        **{key: body[key] for key in ("selection", "patterns", "chapters")},
    }
    if preview_hash(preview) != body["preview_sha256"]:
        raise ValueError("tactical preview hash differs")
    return {"kind": PREVIEW_VERSION, "preview": preview, "preview_sha256": body["preview_sha256"]}


def revalidate(path, envelope, expected):
    preview = _preview(envelope, expected)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    try:
        db = SimpleNamespace(connection=connection)
        budget = Budget(db)
        current = build(
            db, os.environ["CHESS_SUBJECT"], os.environ["CHESS_CORPUS"], preview, budget
        )
        if canonical(current) != canonical(envelope):
            raise ValueError("tactical export changed")
        budget.check()
    finally:
        connection.close()
