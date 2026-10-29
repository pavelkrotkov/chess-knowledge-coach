"""Filter and page versioned, visible puzzles."""

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
    corpus = db.connection.execute(
        "SELECT id,state FROM puzzle_corpora WHERE version=? AND state IN ('legacy_ready','ready')",
        (version,),
    ).fetchone()
    if corpus is None:
        return []
    query, params = _query(corpus["id"], corpus["state"], theme, operation, min_rating, max_rating)
    rows = db.connection.execute(query + " LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
    return [_result(row) for row in rows]


def _query(corpus_id, state, theme, operation, min_rating, max_rating):
    indexed_theme = theme is not None and state == "ready"
    if indexed_theme:
        query = """SELECT p.* FROM puzzle_themes t
        JOIN puzzles p ON p.corpus_id=t.corpus_id AND p.puzzle_id=t.puzzle_id
        WHERE t.corpus_id=? AND t.theme=?"""
        params = [corpus_id, theme]
        order = "t.rating,t.puzzle_id"
        rating = "t.rating"
    else:
        query = "SELECT p.* FROM puzzles p WHERE p.corpus_id=?"
        params = [corpus_id]
        order = "p.rating,p.puzzle_id"
        rating = "p.rating"
        if theme is not None:
            query += " AND EXISTS (SELECT 1 FROM json_each(p.themes_json) WHERE value=?)"
            params.append(theme)
    if operation is not None:
        query += " AND p.objective=?"
        params.append(operation)
    if min_rating is not None:
        query += f" AND {rating}>=?"
        params.append(min_rating)
    if max_rating is not None:
        query += f" AND {rating}<=?"
        params.append(max_rating)
    return query + " ORDER BY " + order, params


def _result(row) -> dict[str, object]:
    return {
        "puzzle_id": row["puzzle_id"],
        "rating": row["rating"],
        "rating_deviation": row["rating_deviation"],
        "themes": json.loads(row["themes_json"]),
        "opening": row["opening"],
        "objective": row["objective"],
    }


def _validate_page(limit: int, offset: int) -> None:
    if limit < 1 or limit > 1000 or offset < 0:
        raise ValueError("limit must be 1..1000 and offset must be non-negative")
