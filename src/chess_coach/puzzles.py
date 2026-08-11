"""Streaming import and adaptive querying for the Lichess puzzle corpus."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import TextIO, cast

from .db import Database

_OBJECTIVES = {"fork": "execute", "backRank": "prevent", "backrank": "prevent", "mate": "calculate"}


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_csv(path: Path) -> tuple[TextIO, subprocess.Popen[str] | None]:
    if path.suffix == ".zst":
        process = subprocess.Popen(
            ["zstd", "--decompress", "--stdout", str(path)],
            stdout=subprocess.PIPE,
            text=True,
        )
        if process.stdout is None:
            raise RuntimeError("zstd did not provide a readable stream")
        return cast(TextIO, process.stdout), process
    return path.open(encoding="utf-8", newline=""), None


def _objective(themes: list[str]) -> str:
    for theme in themes:
        if theme in _OBJECTIVES:
            return _OBJECTIVES[theme]
    return "recognize"


def import_puzzles(db: Database, path: str | Path, *, version: str, batch_size: int = 1000) -> int:
    path = Path(path)
    checksum = _checksum(path)
    db.connection.execute(
        "INSERT OR IGNORE INTO puzzle_corpora(version, source, checksum) VALUES (?, ?, ?)",
        (version, str(path), checksum),
    )
    corpus_row = db.connection.execute(
        "SELECT id FROM puzzle_corpora WHERE version = ?", (version,)
    ).fetchone()
    if corpus_row is None:
        raise ValueError(f"unable to create puzzle corpus {version!r}")
    corpus_id = corpus_row[0]
    imported = 0
    stream, process = _open_csv(path)
    try:
        for row in csv.DictReader(stream):
            themes = row.get("Themes", "").split()
            puzzle_id = row["PuzzleId"]
            db.connection.execute(
                """INSERT OR REPLACE INTO puzzles
                (puzzle_id, corpus_id, fen, source, solution, rating, rating_deviation, opening, themes_json, objective)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    puzzle_id,
                    corpus_id,
                    row["FEN"],
                    row["Moves"],
                    row["Moves"],
                    int(row["Rating"]),
                    int(row["RatingDeviation"]),
                    row.get("OpeningTags") or None,
                    json.dumps(themes),
                    _objective(themes),
                ),
            )
            imported += 1
            if imported % batch_size == 0:
                db.connection.commit()
                db.connection.execute(
                    "UPDATE puzzle_corpora SET imported_rows = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (imported, corpus_id),
                )
                db.connection.commit()
        db.connection.commit()
        db.connection.execute(
            "UPDATE puzzle_corpora SET imported_rows = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (imported, corpus_id),
        )
        db.connection.commit()
    finally:
        stream.close()
        if process is not None and process.wait() != 0:
            raise RuntimeError("zstd decompression failed")
    return imported


def query_puzzles(
    db: Database,
    *,
    version: str,
    theme: str | None = None,
    operation: str | None = None,
    min_rating: int | None = None,
    max_rating: int | None = None,
) -> list[dict[str, object]]:
    query = "SELECT puzzle_id, rating, rating_deviation, themes_json, opening, objective FROM puzzles WHERE corpus_id = (SELECT id FROM puzzle_corpora WHERE version = ?)"
    params: list[object] = [version]
    if theme is not None:
        query += " AND EXISTS (SELECT 1 FROM json_each(puzzles.themes_json) WHERE value = ?)"
        params.append(theme)
    if operation is not None:
        query += " AND objective = ?"
        params.append(operation)
    if min_rating is not None:
        query += " AND rating >= ?"
        params.append(min_rating)
    if max_rating is not None:
        query += " AND rating <= ?"
        params.append(max_rating)
    rows = db.connection.execute(query + " ORDER BY rating, puzzle_id", params).fetchall()
    return [
        {
            "puzzle_id": row["puzzle_id"],
            "rating": row["rating"],
            "rating_deviation": row["rating_deviation"],
            "themes": json.loads(row["themes_json"]),
            "opening": row["opening"],
            "objective": row["objective"],
        }
        for row in rows
    ]
