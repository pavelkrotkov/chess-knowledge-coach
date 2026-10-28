"""Keyset-page deterministic, rating-ordered corpus candidates."""

from .db import Database


def new_page(db: Database, version: str, after: list | None, limit: int):
    count = limit + 1
    if after is None:
        return _fetch(db, version, "", [], count)
    rows = _fetch(
        db, version, " AND p.rating=? AND p.puzzle_id>?", after, count, order="p.puzzle_id"
    )
    if len(rows) < count:
        rows.extend(_fetch(db, version, " AND p.rating>?", [after[0]], count - len(rows)))
    return rows


def _fetch(
    db: Database,
    version: str,
    extra: str,
    values: list,
    limit: int,
    *,
    order: str = "p.rating,p.puzzle_id",
):
    query = """SELECT p.*, c.version FROM puzzles p JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? AND p.rating>=0"""
    query += extra + f" ORDER BY {order} LIMIT ?"
    return list(db.connection.execute(query, [version, *values, limit]).fetchall())
