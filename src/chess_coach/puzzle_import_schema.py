"""Versioned corpus staging, searchable prompt metadata and visibility guards."""

import sqlite3

from .puzzle_import_triggers import install_corpus_triggers


def add_corpus_staging(connection: sqlite3.Connection) -> None:
    connection.execute(
        "ALTER TABLE puzzle_corpora ADD COLUMN state TEXT NOT NULL DEFAULT 'legacy_ready' "
        "CHECK(state IN ('legacy_ready','staging','ready','failed'))"
    )
    for definition in (
        "popularity INTEGER",
        "play_count INTEGER",
        "prompt_fen TEXT",
        "prompt_key TEXT",
        "prompt_turn TEXT",
    ):
        connection.execute("ALTER TABLE puzzles ADD COLUMN " + definition)
    connection.execute(
        """CREATE TABLE puzzle_imports (
        corpus_id INTEGER PRIMARY KEY REFERENCES puzzle_corpora(id),
        csv_path TEXT NOT NULL, csv_sha256 TEXT NOT NULL, archive_sha256 TEXT,
        source_url TEXT, importer_version TEXT NOT NULL, header_json TEXT NOT NULL,
        byte_offset INTEGER NOT NULL, row_number INTEGER NOT NULL DEFAULT 1,
        accepted INTEGER NOT NULL DEFAULT 0, rejected INTEGER NOT NULL DEFAULT 0,
        error TEXT
        )"""
    )
    connection.execute(
        """CREATE TABLE puzzle_import_seen (
        corpus_id INTEGER NOT NULL REFERENCES puzzle_corpora(id),
        puzzle_id TEXT NOT NULL, PRIMARY KEY(corpus_id,puzzle_id)
        )"""
    )
    connection.execute(
        """CREATE TABLE puzzle_themes (
        corpus_id INTEGER NOT NULL, puzzle_id TEXT NOT NULL, theme TEXT NOT NULL,
        rating INTEGER NOT NULL, PRIMARY KEY(corpus_id,puzzle_id,theme),
        FOREIGN KEY(corpus_id,puzzle_id) REFERENCES puzzles(corpus_id,puzzle_id) ON DELETE CASCADE
        )"""
    )
    connection.execute(
        """CREATE TABLE puzzle_theme_counts (
        corpus_id INTEGER NOT NULL REFERENCES puzzle_corpora(id),
        theme TEXT NOT NULL, count INTEGER NOT NULL,
        PRIMARY KEY(corpus_id,theme)
        )"""
    )
    connection.execute(
        "CREATE INDEX idx_puzzle_themes_search ON puzzle_themes(corpus_id,theme,rating,puzzle_id)"
    )
    connection.execute("CREATE INDEX idx_puzzles_prompt ON puzzles(corpus_id,prompt_key,puzzle_id)")
    connection.execute(
        "CREATE INDEX idx_puzzles_prompt_turn ON puzzles(corpus_id,prompt_turn,rating,puzzle_id)"
    )
    install_corpus_triggers(connection)
