"""Insert validated puzzle records and aggregate normalized theme counts."""

import json
from collections import Counter

from .db import Database


def insert_puzzles(db: Database, corpus_id: int, rows: list[dict]) -> None:
    db.connection.executemany(
        """INSERT INTO puzzles(corpus_id,puzzle_id,fen,source,solution,rating,rating_deviation,
        opening,themes_json,objective,popularity,play_count,prompt_fen,prompt_key,prompt_turn,prompt_material)
        VALUES (?,?,?,?,?,?,?,?,?,'unknown',?,?,?,?,?,?)""",
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
                r["prompt_material"],
            )
            for r in rows
        ],
    )


def insert_themes(db: Database, corpus_id: int, rows: list[dict]) -> None:
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
