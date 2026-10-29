"""Persist a staging batch and its checkpoint in one short SQLite transaction."""

from .db import Database
from .puzzle_import_inserts import insert_puzzles, insert_themes


def save_batch(
    db: Database, corpus_id: int, offset: int, next_offset: int, rows: list[dict]
) -> None:
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        current = db.connection.execute(
            "SELECT byte_offset,row_number FROM puzzle_imports WHERE corpus_id=?", (corpus_id,)
        ).fetchone()
        if current is None or current["byte_offset"] != offset:
            raise ValueError("corpus checkpoint changed")
        db.connection.executemany(
            "INSERT INTO puzzle_import_seen(corpus_id,puzzle_id,record_number,valid) VALUES (?,?,?,?)",
            [
                (corpus_id, row["puzzle_id"], current["row_number"] + index + 1, int(row["valid"]))
                for index, row in enumerate(rows)
            ],
        )
        valid = [row for row in rows if row["valid"]]
        insert_puzzles(db, corpus_id, valid)
        insert_themes(db, corpus_id, valid)
        db.connection.execute(
            """UPDATE puzzle_imports SET byte_offset=?,row_number=row_number+?,
            accepted=accepted+?,rejected=rejected+? WHERE corpus_id=?""",
            (next_offset, len(rows), len(valid), len(rows) - len(valid), corpus_id),
        )
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise
