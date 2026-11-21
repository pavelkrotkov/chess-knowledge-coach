"""Require a ready, attributed public puzzle corpus."""

from urllib.parse import urlparse


def licensed(db, corpus):
    row = db.connection.execute(
        "SELECT id, source, checksum FROM puzzle_corpora WHERE version=? AND state='ready'",
        (corpus,),
    ).fetchone()
    if row is None or not row["checksum"] or not isinstance(row["source"], str):
        return None
    parsed = urlparse(row["source"])
    if parsed.scheme != "https" or parsed.hostname != "database.lichess.org":
        return None
    return row
