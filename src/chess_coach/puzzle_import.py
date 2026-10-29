"""Bounded, resumable import of decoded, checksum-pinned puzzle CSV files."""

import sqlite3
from pathlib import Path

from .db import Database
from .puzzle_import_csv import header, read_batch
from .puzzle_import_input import check_digest, import_lock, snapshot_path, verify_snapshot
from .puzzle_import_state import corpus_report, fail, initialize
from .puzzle_import_store import finish, save_batch

OFFICIAL_SOURCE = "https://database.lichess.org/lichess_db_puzzle.csv.zst"


def stage_puzzles(
    db: Database,
    path: str | Path,
    *,
    project_root: str | Path,
    version: str,
    csv_sha256: str,
    archive_sha256: str | None = None,
    source_url: str | None = None,
    max_rows: int = 1000,
    batch_size: int = 100,
) -> dict:
    """Process at most max_rows records (zero means through EOF) in bounded commits."""
    _validate(db, version, csv_sha256, archive_sha256, source_url, max_rows, batch_size)
    with import_lock(db.path, project_root):
        source = snapshot_path(path, project_root)
        verify_snapshot(source, csv_sha256)
        fields, offset = header(source)
        corpus_id = initialize(
            db, version, str(source), csv_sha256, archive_sha256, source_url, fields, offset
        )
        return _run(db, source, corpus_id, csv_sha256, fields, max_rows, batch_size)


def _validate(db, version, csv_sha256, archive_sha256, source_url, max_rows, batch_size):
    if db.connection.in_transaction:
        raise RuntimeError("cannot import during an existing transaction")
    if not version or len(version) > 256:
        raise ValueError("a version of at most 256 characters is required")
    check_digest(csv_sha256)
    if not csv_sha256:
        raise ValueError("decoded CSV checksum is required")
    check_digest(archive_sha256)
    if source_url not in {None, OFFICIAL_SOURCE}:
        raise ValueError("only the official puzzle archive URL is supported")
    if not 0 <= max_rows <= 100_000_000 or not 1 <= batch_size <= 500:
        raise ValueError("invalid import bounds")


def _run(db, source, corpus_id, digest, fields, max_rows, batch_size):
    row = db.connection.execute(
        """SELECT c.state,i.byte_offset FROM puzzle_corpora c
        JOIN puzzle_imports i ON i.corpus_id=c.id WHERE c.id=?""",
        (corpus_id,),
    ).fetchone()
    if row["state"] == "ready":
        return _single_report(db, corpus_id)
    offset = row["byte_offset"]
    remaining = max_rows
    try:
        while not max_rows or remaining > 0:
            limit = min(batch_size, remaining) if max_rows else batch_size
            rows, next_offset, eof = read_batch(source, offset, fields, limit)
            if rows:
                save_batch(db, corpus_id, offset, next_offset, rows)
                remaining -= len(rows)
                offset = next_offset
            if eof:
                verify_snapshot(source, digest)
                finish(db, corpus_id, offset)
                break
            if not rows:
                raise ValueError("CSV checkpoint did not advance")
    except (ValueError, OSError, sqlite3.IntegrityError):
        fail(db, corpus_id, "source is invalid, changed, or contains duplicate IDs")
        raise ValueError(
            "corpus import stopped; source is invalid, changed, or has duplicate IDs"
        ) from None
    return _single_report(db, corpus_id)


def _single_report(db: Database, corpus_id: int) -> dict:
    version = db.connection.execute(
        "SELECT version FROM puzzle_corpora WHERE id=?", (corpus_id,)
    ).fetchone()[0]
    return next(item for item in corpus_report(db) if item["version"] == version)
