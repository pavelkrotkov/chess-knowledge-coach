"""Read one exact ordered branch from a bounded immutable public index."""

import json
import sqlite3
import time

from .named_structures import VERSION as STRUCTURE_VERSION
from .opening_profile_center import summarize as center_summary
from .opening_profile_play import PARENT_PLIES, STORED_PLIES, WINDOW_PLIES
from .opening_profile_store import TRANSFORM
from .opening_reference_source import (
    LICENSE,
    LICENSE_URL,
    SOURCE,
    SOURCE_ARCHIVE,
    SOURCE_MONTH,
    SOURCE_SHA256,
)
from .opening_snapshot import GRAPH_SHA256, VERSION

MAX_GAMES = 10


def guard(db, expires):
    if expires is not None:
        db.set_progress_handler(lambda: int(time.monotonic() >= expires), 1000)


def lookup(path, parent, move, *, expires=None):
    db = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        guard(db, expires)
        metadata = {
            k: json.loads(v) for k, v in db.execute("SELECT key,value FROM metadata LIMIT 32")
        }
        _validate(metadata)
        rows = db.execute(
            """SELECT game_id,MIN(ply) FROM moves WHERE parent=? AND uci=? AND ply<=?
            GROUP BY game_id ORDER BY game_id LIMIT ?""",
            (parent, move, PARENT_PLIES, MAX_GAMES + 1),
        ).fetchall()
        from .opening_profile_summary import summarize

        summary = summarize(db, rows[:MAX_GAMES])
        return {
            **summary,
            "center": center_summary(db, rows[:MAX_GAMES], parent, move),
            "more_matches": len(rows) > MAX_GAMES,
            "coverage": metadata["coverage"],
            "source": SOURCE,
            "license": LICENSE,
            "license_url": LICENSE_URL,
            "source_sha256": SOURCE_SHA256,
        }
    finally:
        db.close()


def _validate(metadata):
    expected = {
        "source_sha256": SOURCE_SHA256,
        "source_url": SOURCE,
        "source_archive": SOURCE_ARCHIVE,
        "source_month": SOURCE_MONTH,
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "transform": TRANSFORM,
        "opening_graph": GRAPH_SHA256,
        "opening_version": VERSION,
        "structure_version": STRUCTURE_VERSION,
        "parent_plies": PARENT_PLIES,
        "window_plies": WINDOW_PLIES,
        "stored_plies": STORED_PLIES,
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError("ordered profile source differs")
    if not isinstance(metadata.get("coverage"), dict):
        raise ValueError("ordered profile coverage unavailable")
