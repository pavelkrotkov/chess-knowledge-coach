"""Filter and page versioned, visible puzzles."""

from __future__ import annotations

import json

from .db import Database
from .puzzle_query_page import validate_cursor, validate_page
from .puzzle_query_sql import build_query as _query


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
    after_rating: int | None = None,
    after_id: str | None = None,
) -> list[dict[str, object]]:
    validate_page(limit, offset)
    validate_cursor(after_rating, after_id, offset)
    corpus = db.connection.execute(
        "SELECT id,state FROM puzzle_corpora WHERE version=? AND state IN ('legacy_ready','ready')",
        (version,),
    ).fetchone()
    if corpus is None:
        return []
    if corpus["state"] == "ready" and operation not in (None, "unknown"):
        return []
    if corpus["state"] == "ready" and offset > 1000:
        raise ValueError("use keyset pagination after offset 1000")
    query, params = _query(
        corpus["id"],
        corpus["state"],
        theme,
        operation,
        min_rating,
        max_rating,
        after_rating,
        after_id,
    )
    rows = db.connection.execute(query + " LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
    return [_result(row) for row in rows]


def _result(row) -> dict[str, object]:
    return {
        "puzzle_id": row["puzzle_id"],
        "rating": row["rating"],
        "rating_deviation": row["rating_deviation"],
        "themes": json.loads(row["themes_json"]),
        "opening": row["opening"],
        "objective": row["objective"],
    }
