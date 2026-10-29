"""Versioned opening dataset import and transposition-aware classification."""

from __future__ import annotations

from pathlib import Path

from .db import Database
from .opening_classification import classify_game as classify_game
from .opening_rows import _rows
from .opening_storage import _import_row
from .opening_storage import position_key as position_key


def import_openings(
    db: Database,
    path: str | Path,
    *,
    version: str,
    source_url: str,
) -> int:
    """Import ECO/name/moves or ECO/name/pgn rows into a position DAG."""
    return import_rows(db, _rows(path), version=version, source_url=source_url)


def import_rows(db, rows, *, version, source_url):
    """Atomically add rows to a versioned dataset."""
    try:
        db.connection.execute(
            "INSERT OR IGNORE INTO opening_datasets(version, source_url) VALUES (?, ?)",
            (version, source_url),
        )
        dataset_id = db.connection.execute(
            "SELECT id FROM opening_datasets WHERE version = ? AND source_url = ?",
            (version, source_url),
        ).fetchone()
        if dataset_id is None:
            raise ValueError(f"failed to insert or find dataset {version!r}")
        dataset_id = dataset_id[0]
        previous_changes = db.connection.total_changes
        for row_number, row in enumerate(rows, start=1):
            _import_row(db, dataset_id, row, row_number)
        if db.connection.total_changes != previous_changes:
            db.connection.execute(
                "UPDATE opening_datasets SET content_revision=content_revision+1 WHERE id=?",
                (dataset_id,),
            )
        imported = len(rows)
        db.connection.commit()
        return imported
    except Exception:
        db.connection.rollback()
        raise
