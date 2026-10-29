"""Read, validate and commit bounded batches; publish only verified EOF."""

import sqlite3

from .puzzle_import_budget import check_reserve
from .puzzle_import_csv import read_batch
from .puzzle_import_failure import record_failure
from .puzzle_import_input import verify_snapshot
from .puzzle_import_publish import finish
from .puzzle_import_report import report_one
from .puzzle_import_source import unchanged
from .puzzle_import_store import save_batch


def run(db, source, corpus_id, digest, fields, max_rows, batch_size, signature, min_free_bytes):
    row = db.connection.execute(
        """SELECT c.state,i.byte_offset FROM puzzle_corpora c
        JOIN puzzle_imports i ON i.corpus_id=c.id WHERE c.id=?""",
        (corpus_id,),
    ).fetchone()
    if row["state"] == "ready":
        return report_one(db, corpus_id)
    offset = row["byte_offset"]
    remaining = max_rows
    try:
        while not max_rows or remaining > 0:
            limit = min(batch_size, remaining) if max_rows else batch_size
            check_reserve(db.path.parent, min_free_bytes)
            offset, count, eof = _step(db, source, corpus_id, fields, offset, limit, signature)
            remaining -= count
            if eof:
                verify_snapshot(source, digest)
                unchanged(source, signature)
                finish(db, corpus_id, offset)
                break
            if not count:
                raise ValueError("CSV checkpoint did not advance")
    except (ValueError, OSError, sqlite3.IntegrityError) as exc:
        record_failure(db, corpus_id, exc)
    return report_one(db, corpus_id)


def _step(db, source, corpus_id, fields, offset, limit, signature):
    unchanged(source, signature)
    rows, next_offset, eof = read_batch(source, offset, fields, limit)
    unchanged(source, signature)
    if rows:
        save_batch(db, corpus_id, offset, next_offset, rows)
    return next_offset, len(rows), eof
