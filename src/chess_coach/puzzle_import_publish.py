"""Publish a complete staged corpus with constant-time reconciliation."""

from .db import Database


def finish(db: Database, corpus_id: int, expected_offset: int) -> None:
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        row = db.connection.execute(
            "SELECT byte_offset,row_number,accepted,rejected FROM puzzle_imports WHERE corpus_id=?",
            (corpus_id,),
        ).fetchone()
        if row is None or row["byte_offset"] != expected_offset or row["accepted"] == 0:
            raise ValueError("corpus is incomplete or has no valid puzzles")
        if row["accepted"] + row["rejected"] != row["row_number"] - 1:
            raise ValueError("corpus row counts do not reconcile")
        changed = db.connection.execute(
            "UPDATE puzzle_corpora SET imported_rows=?,state='ready',updated_at=CURRENT_TIMESTAMP WHERE id=? AND state='staging'",
            (row["accepted"], corpus_id),
        )
        if changed.rowcount != 1:
            raise ValueError("corpus is not staging")
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise
