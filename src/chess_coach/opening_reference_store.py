"""Build the independent indexed public-reference artifact."""

import json
import sqlite3

from .opening_reference_source import (
    LICENSE,
    LICENSE_URL,
    SOURCE,
    SOURCE_ARCHIVE,
    SOURCE_MONTH,
    SOURCE_SHA256,
    TRANSFORM,
)
from .opening_snapshot import GRAPH_SHA256, VERSION


def store(path, records, coverage):
    db = sqlite3.connect(path)
    try:
        db.executescript("""
            PRAGMA journal_mode=MEMORY;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE games (id INTEGER PRIMARY KEY, context TEXT NOT NULL, site TEXT NOT NULL);
            CREATE TABLE positions (key TEXT NOT NULL, game_id INTEGER NOT NULL, san TEXT NOT NULL, uci TEXT NOT NULL);
            CREATE INDEX reference_position ON positions(key, game_id);
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
            "coverage": coverage,
        }
        db.executemany(
            "INSERT INTO metadata VALUES (?,?)", [(k, json.dumps(v)) for k, v in metadata.items()]
        )
        for _, number, context, site, positions, _ in records:
            db.execute("INSERT INTO games VALUES (?,?,?)", (number, json.dumps(context), site))
            db.executemany(
                "INSERT INTO positions VALUES (?,?,?,?)",
                [(key, number, san, uci) for key, san, uci in positions],
            )
        db.commit()
    finally:
        db.close()
