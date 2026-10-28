"""Index the bounded rating-ordered puzzle scan."""

import sqlite3


def add_curriculum_index(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_puzzles_curriculum ON puzzles(corpus_id, rating, puzzle_id)"
    )
