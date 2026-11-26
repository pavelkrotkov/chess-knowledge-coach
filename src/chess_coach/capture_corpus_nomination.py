"""Advance a finite corpus-version horizon for one nominated context."""

from .capture_corpus_context import context as nominate_context
from .capture_public_index import available
from .capture_public_page import initial as public_initial


def _version(db, context):
    preferred = context["preferred"]
    if context["first"]:
        context["first"] = False
        row = db.connection.execute(
            "SELECT id,version,checksum FROM puzzle_corpora WHERE version=? AND version<=? AND state='ready'",
            (preferred, context["ceiling"]),
        ).fetchone()
        if row is not None:
            return row
    return db.connection.execute(
        """SELECT id,version,checksum FROM puzzle_corpora WHERE state='ready'
        AND version>? AND version<=? AND version!=? ORDER BY version LIMIT 1""",
        (context["last"], context["ceiling"], preferred),
    ).fetchone()


def build(db, subject, data, progress, check):
    if not available(db):
        return False
    context, visited = nominate_context(db, subject, progress, check)
    if context is None:
        return visited
    corpus = _version(db, context)
    if corpus is None:
        progress["context"] = None
        return visited
    if corpus["version"] != context["preferred"]:
        context["last"] = corpus["version"]
    scope = [corpus["version"], corpus["checksum"], context["lower"], context["upper"]]
    building = {
        "scope": scope,
        "corpus_id": corpus["id"],
        "band": 0,
        "count": 0,
        "last": None,
        "keys": [],
        "limited": False,
        "pending": [],
        "public": public_initial(subject),
    }
    data["prior"] = {"building": building, "entries": {}}
    return visited
