"""Bounded, resumable import of decoded, checksum-pinned puzzle CSV files."""

from pathlib import Path

from .db import Database
from .puzzle_import_budget import validate_reserve
from .puzzle_import_csv import header
from .puzzle_import_input import check_digest
from .puzzle_import_lock import import_lock
from .puzzle_import_run import run
from .puzzle_import_source import configure_wal, source_snapshot, unchanged
from .puzzle_import_state import initialize

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
    enable_wal: bool = False,
    min_free_bytes: int = 10 * 1024**3,
) -> dict:
    """Process at most max_rows records (zero means through EOF) in bounded commits."""
    _validate(db, version, csv_sha256, archive_sha256, source_url, max_rows, batch_size)
    validate_reserve(min_free_bytes)
    with import_lock(db.path, project_root):
        configure_wal(db, enable_wal)
        source, source_signature = source_snapshot(db, path, project_root, version, csv_sha256)
        fields, offset = header(source)
        unchanged(source, source_signature)
        corpus_id = initialize(
            db, version, str(source), csv_sha256, archive_sha256, source_url, fields, offset
        )
        return run(
            db,
            source,
            corpus_id,
            csv_sha256,
            fields,
            max_rows,
            batch_size,
            source_signature,
            min_free_bytes,
        )


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
