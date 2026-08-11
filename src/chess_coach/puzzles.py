"""Streaming import and adaptive querying for the Lichess puzzle corpus."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from itertools import chain
from pathlib import Path
from typing import TextIO, cast

from .db import Database

_FIELDS = [
    "PuzzleId",
    "FEN",
    "Moves",
    "Rating",
    "RatingDeviation",
    "Popularity",
    "NbPlays",
    "Themes",
    "GameUrl",
    "OpeningTags",
]
_OBJECTIVES = {"fork": "execute", "backRankMate": "prevent", "mate": "calculate"}


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_csv(path: Path) -> tuple[TextIO, subprocess.Popen[str] | None]:
    if path.suffix == ".zst":
        try:
            process = subprocess.Popen(
                ["zstd", "--decompress", "--stdout", str(path)],
                stdout=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            raise RuntimeError(f"zstd command not found or failed to start: {exc}") from exc
        if process.stdout is None:
            raise RuntimeError("zstd did not provide a readable stream")
        return cast(TextIO, process.stdout), process
    return path.open(encoding="utf-8", newline=""), None


def _objective(themes: list[str]) -> str:
    for theme in themes:
        if theme in _OBJECTIVES:
            return _OBJECTIVES[theme]
    return "recognize"


def _reader(stream: TextIO) -> csv.DictReader[str]:
    first = stream.readline()
    if not first:
        return csv.DictReader([], fieldnames=_FIELDS)
    lines = chain([first], stream)
    if first.split(",", 1)[0].strip() == "PuzzleId":
        return csv.DictReader(lines)
    return csv.DictReader(lines, fieldnames=_FIELDS)


def import_puzzles(db: Database, path: str | Path, *, version: str, batch_size: int = 1000) -> int:
    path = Path(path)
    checksum = _checksum(path)
    existing = db.connection.execute(
        "SELECT id, checksum FROM puzzle_corpora WHERE version = ?", (version,)
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
        reader = _reader(stream)
        required = {"PuzzleId", "FEN", "Moves", "Rating", "RatingDeviation"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV missing required columns: {sorted(required)}")
        for row in reader:
            themes = row.get("Themes", "").split()
            db.connection.execute(
                """INSERT INTO puzzles
                (puzzle_id, corpus_id, fen, source, solution, rating, rating_deviation, opening, themes_json, objective)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["PuzzleId"],
                    corpus_id,
                    row["FEN"],
                    row.get("GameUrl", ""),
                    row["Moves"],
                    int(row["Rating"]),
                    int(row["RatingDeviation"]),
                    row.get("OpeningTags") or None,
                    json.dumps(themes),
                    _objective(themes),
                ),
            )
            imported += 1
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
        db.connection.execute("DELETE FROM puzzles WHERE corpus_id = ?", (corpus_id,))
        db.connection.execute("DELETE FROM puzzle_corpora WHERE id = ?", (corpus_id,))
        db.connection.commit()
        raise
    finally:
        try:
            stream.close()
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()


def query_puzzles(
    db: Database,
    *,
    version: str,
    theme: str | None = None,
    operation: str | None = None,
    min_rating: int | None = None,
    max_rating: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, object]]:
    if limit < 1 or limit > 1000 or offset < 0:
        raise ValueError("limit must be 1..1000 and offset must be non-negative")
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
    rows = db.connection.execute(
        query + " ORDER BY rating, puzzle_id LIMIT ? OFFSET ?", [*params, limit, offset]
    ).fetchall()
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
