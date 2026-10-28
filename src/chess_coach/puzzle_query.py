"""Filter and page imported puzzles."""

from __future__ import annotations

import json

from .db import Database


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
    _validate_page(limit, offset)
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


def _validate_page(limit: int, offset: int) -> None:
    if limit < 1 or limit > 1000 or offset < 0:
        raise ValueError("limit must be 1..1000 and offset must be non-negative")
