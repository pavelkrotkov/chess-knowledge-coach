"""Validate and store puzzle CSV rows."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TextIO

from .db import Database
from .puzzle_csv import _reader

_OBJECTIVES = {"fork": "execute", "backRankMate": "prevent", "mate": "calculate"}


def _objective(themes: Sequence[str]) -> str:
    for theme in themes:
        if theme in _OBJECTIVES:
            return _OBJECTIVES[theme]
    return "recognize"


_REQUIRED = {"PuzzleId", "FEN", "Moves", "Rating", "RatingDeviation"}


def import_rows(db: Database, stream: TextIO, corpus_id: int) -> int:
    reader = _reader(stream)
    if reader.fieldnames is None or not _REQUIRED.issubset(reader.fieldnames):
        raise ValueError(f"CSV missing required columns: {sorted(_REQUIRED)}")
    imported = 0
    for row in reader:
        _insert_row(db, corpus_id, row, reader.line_num)
        imported += 1
    return imported


def _insert_row(db: Database, corpus_id: int, row: dict[str, str], line_num: int) -> None:
    missing = [field for field in sorted(_REQUIRED) if not (row.get(field) or "").strip()]
    if missing:
        raise ValueError(f"puzzle row {line_num} is missing required fields: {missing}")
    themes = list((row.get("Themes") or "").split())
    db.connection.execute(
        """INSERT INTO puzzles
        (puzzle_id, corpus_id, fen, source, solution, rating, rating_deviation, opening, themes_json, objective)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            row["PuzzleId"],
            corpus_id,
            row["FEN"],
            row.get("GameUrl") or "",
            row["Moves"],
            int(row["Rating"]),
            int(row["RatingDeviation"]),
            row.get("OpeningTags") or None,
            json.dumps(themes),
            _objective(themes),
        ),
    )
