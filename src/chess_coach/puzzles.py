"""Streaming import and adaptive querying for the Lichess puzzle corpus."""

from __future__ import annotations

from pathlib import Path
from subprocess import Popen
from typing import TextIO

from .db import Database
from .puzzle_csv import _checksum, _open_csv
from .puzzle_query import query_puzzles as query_puzzles
from .puzzle_rows import import_rows


def import_puzzles(db: Database, path: str | Path, *, version: str, batch_size: int = 1000) -> int:
    path = Path(path)
    checksum = _checksum(path)
    existing = db.connection.execute(
        "SELECT id, checksum, imported_rows FROM puzzle_corpora WHERE version = ?", (version,)
    ).fetchone()
    if existing is not None and existing["checksum"] != checksum:
        raise ValueError(f"corpus version {version!r} already exists with a different checksum")
    db.connection.execute(
        "INSERT OR IGNORE INTO puzzle_corpora(version, source, checksum) VALUES (?, ?, ?)",
        (version, str(path), checksum),
    )
    corpus = db.connection.execute(
        "SELECT id FROM puzzle_corpora WHERE version = ?", (version,)
    ).fetchone()
    if corpus is None:
        raise ValueError(f"unable to create puzzle corpus {version!r}")
    corpus_id = corpus[0]
    db.connection.execute("DELETE FROM puzzles WHERE corpus_id = ?", (corpus_id,))
    imported = 0
    stream, process = _open_csv(path)
    try:
        imported = import_rows(db, stream, corpus_id)
        if process is not None and process.wait() != 0:
            raise RuntimeError("zstd decompression failed")
        db.connection.execute(
            "UPDATE puzzle_corpora SET source = ?, imported_rows = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (str(path), imported, corpus_id),
        )
        db.connection.commit()
        return imported
    except Exception:
        db.connection.rollback()
        if existing is None:
            # A brand-new corpus that failed validation leaves nothing behind.
            db.connection.execute("DELETE FROM puzzles WHERE corpus_id = ?", (corpus_id,))
            db.connection.execute("DELETE FROM puzzle_corpora WHERE id = ?", (corpus_id,))
        else:
            # Re-import of an existing corpus: restore its previous rows so a
            # bad file never wipes good data.
            db.connection.execute(
                "UPDATE puzzle_corpora SET imported_rows = ? WHERE id = ?",
                (existing["imported_rows"], corpus_id),
            )
        db.connection.commit()
        raise
    finally:
        _close_stream(stream, process)


def _close_stream(stream: TextIO, process: Popen[str] | None) -> None:
    try:
        stream.close()
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
