"""Read the source and selected corpus rating inputs used at admission."""

from .related_capture_context import rating


def read(db, corpus, key, position, side):
    row = db.connection.execute(
        """SELECT p.rating,p.rating_deviation,c.checksum FROM puzzles p
        JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? AND c.state='ready' AND p.puzzle_id=?""",
        (corpus, key),
    ).fetchone()
    if row is None:
        return None
    return (rating(db, position, side), row["rating"], row["rating_deviation"], row["checksum"])
