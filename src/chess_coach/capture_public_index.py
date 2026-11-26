"""Read one indexed public collection or task under the worker deadline."""

from .capture_corpus_storage import POLICY
from .fact_fingerprint import canonical, digest
from .public_training_line import PUBLIC_LINE_PLIES_LIMIT
from .public_training_query import task as read_task
from .public_training_query import tasks
from .unified_sources import resolve_source


def collection(db, after, check):
    check()
    row = db.connection.execute(
        """SELECT version,source_url,source_revision,source_sha256,content_sha256,
        content_format,license,attribution,accepted,excluded FROM public_collections
        WHERE state='ready' AND version>? ORDER BY version LIMIT 1""",
        (after,),
    ).fetchone()
    check()
    return dict(row) if row else None


def task(db, version, after, check):
    check()
    rows = tasks(db, version, limit=1, after_id=after)
    check()
    return rows[0] if rows else None


FIELDS = (
    "source_url",
    "source_revision",
    "source_sha256",
    "content_sha256",
    "license",
    "attribution",
    "license_notice",
)


def bind(db, version, key, check):
    check()
    raw = read_task(db, version, key)
    if raw is None:
        raise ValueError("public capture unavailable")
    source = resolve_source(db, "public", version, key)
    check()
    candidate = {
        "type": "public",
        "version": version,
        "key": key,
        "origin": {field: raw[field] for field in FIELDS},
        "raw_fen": raw["prompt_fen"],
        "raw_line": raw["lines"][0],
        "fen": source["prompt_fen"],
        "objective": source["objective"],
        "line": source["lines"][0],
        "history": "standalone",
    }
    return digest(canonical(["public", POLICY, PUBLIC_LINE_PLIES_LIMIT, candidate])), candidate
