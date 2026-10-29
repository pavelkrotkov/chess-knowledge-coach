"""Persist a staging batch and its checkpoint in one short SQLite transaction."""

import json
from collections import Counter

from .db import Database


def save_batch(
    db: Database, corpus_id: int, offset: int, next_offset: int, rows: list[dict]
) -> None:
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        current = db.connection.execute(
            "SELECT byte_offset FROM puzzle_imports WHERE corpus_id=?", (corpus_id,)
        ).fetchone()
        if current is None or current["byte_offset"] != offset:
            raise ValueError("corpus checkpoint changed")
        db.connection.executemany(
            "INSERT INTO puzzle_import_seen(corpus_id,puzzle_id) VALUES (?,?)",
            [(corpus_id, row["puzzle_id"]) for row in rows],
        )
        valid = [row for row in rows if row["valid"]]
        _insert_puzzles(db, corpus_id, valid)
        _insert_themes(db, corpus_id, valid)
        db.connection.execute(
            """UPDATE puzzle_imports SET byte_offset=?,row_number=row_number+?,
            accepted=accepted+?,rejected=rejected+? WHERE corpus_id=?""",
            (next_offset, len(rows), len(valid), len(rows) - len(valid), corpus_id),
        )
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise


def _insert_puzzles(db: Database, corpus_id: int, rows: list[dict]) -> None:
    db.connection.executemany(
        """INSERT INTO puzzles(corpus_id,puzzle_id,fen,source,solution,rating,rating_deviation,
        opening,themes_json,objective,popularity,play_count,prompt_fen,prompt_key,prompt_turn)
        VALUES (?,?,?,?,?,?,?,?,?,'unknown',?,?,?,?,?)""",
        [
            (
                corpus_id,
                r["puzzle_id"],
                r["fen"],
                r["source"],
                r["solution"],
                r["rating"],
                r["deviation"],
                r["opening"],
                json.dumps(r["themes"]),
                r["popularity"],
                r["play_count"],
                r["prompt_fen"],
                r["prompt_key"],
                r["prompt_turn"],
            )
            for r in rows
        ],
    )


def _insert_themes(db: Database, corpus_id: int, rows: list[dict]) -> None:
    entries = [
        (corpus_id, row["puzzle_id"], theme, row["rating"])
        for row in rows
        for theme in row["themes"]
    ]
    db.connection.executemany(
        "INSERT INTO puzzle_themes(corpus_id,puzzle_id,theme,rating) VALUES (?,?,?,?)", entries
    )
    counts = Counter(theme for row in rows for theme in row["themes"])
    db.connection.executemany(
        """INSERT INTO puzzle_theme_counts(corpus_id,theme,count) VALUES (?,?,?)
        ON CONFLICT(corpus_id,theme) DO UPDATE SET count=count+excluded.count""",
        [(corpus_id, theme, count) for theme, count in counts.items()],
    )


def finish(db: Database, corpus_id: int, expected_offset: int) -> None:
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        row = db.connection.execute(
            "SELECT byte_offset,accepted,rejected FROM puzzle_imports WHERE corpus_id=?",
            (corpus_id,),
        ).fetchone()
        if row is None or row["byte_offset"] != expected_offset or row["accepted"] == 0:
            raise ValueError("corpus is incomplete or has no valid puzzles")
        if row["accepted"] + row["rejected"] < 1:
            raise ValueError("corpus row counts do not reconcile")
        db.connection.execute(
            "UPDATE puzzle_corpora SET imported_rows=?,state='ready',updated_at=CURRENT_TIMESTAMP WHERE id=? AND state='staging'",
            (row["accepted"], corpus_id),
        )
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise
