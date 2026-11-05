"""Resolve a private, source-bound corpus seek anchor."""

from .related_mate_search_token import fingerprint


def position(db, corpus, key, lower, upper, secret):
    if key == 0:
        return lower, ""
    try:
        rowid, signature = key
        row = db.connection.execute(
            """SELECT rating,puzzle_id FROM puzzle_themes
            WHERE rowid=? AND corpus_id=? AND theme='mateIn2' AND rating BETWEEN ? AND ?""",
            (rowid, corpus["id"], lower, upper),
        ).fetchone()
        if (
            row is None
            or fingerprint(secret, "anchor", [rowid, row["rating"], row["puzzle_id"]]) != signature
        ):
            raise ValueError
        return row["rating"], row["puzzle_id"]
    except (ValueError, TypeError):
        raise ValueError("search boundary changed; restart") from None
