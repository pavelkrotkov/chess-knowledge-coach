"""Build a separate ordered, bounded public opening profile index."""

import json
import sqlite3

from .named_structures import VERSION as STRUCTURE_VERSION
from .opening_profile_play import PARENT_PLIES, STORED_PLIES, WINDOW_PLIES
from .opening_reference_source import (
    LICENSE,
    LICENSE_URL,
    SOURCE,
    SOURCE_ARCHIVE,
    SOURCE_MONTH,
    SOURCE_SHA256,
)
from .opening_snapshot import GRAPH_SHA256, VERSION

TRANSFORM = "v2:32MB-decoded;5000-records;1000-games;40-parent-plies;12-window-plies;512-game-plies"


def store(path, records, coverage):
    db = sqlite3.connect(path)
    try:
        db.executescript("""
            PRAGMA journal_mode=MEMORY;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE games (id INTEGER PRIMARY KEY, context TEXT NOT NULL, site TEXT NOT NULL, total_plies INTEGER NOT NULL);
            CREATE TABLE moves (game_id INTEGER NOT NULL, ply INTEGER NOT NULL, parent TEXT NOT NULL,
                san TEXT NOT NULL, uci TEXT NOT NULL, shapes TEXT NOT NULL, PRIMARY KEY(game_id,ply));
            CREATE INDEX profile_edge ON moves(parent,uci,game_id,ply);
        """)
        metadata = {
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
            "coverage": coverage,
        }
        db.executemany(
            "INSERT INTO metadata VALUES (?,?)", [(k, json.dumps(v)) for k, v in metadata.items()]
        )
        for _, number, context, site, positions, _, total in records:
            db.execute(
                "INSERT INTO games VALUES (?,?,?,?)", (number, json.dumps(context), site, total)
            )
            db.executemany(
                "INSERT INTO moves VALUES (?,?,?,?,?,?)",
                [
                    (number, ply, parent, san, uci, json.dumps(shapes))
                    for ply, parent, san, uci, shapes in positions
                ],
            )
        db.commit()
    finally:
        db.close()
