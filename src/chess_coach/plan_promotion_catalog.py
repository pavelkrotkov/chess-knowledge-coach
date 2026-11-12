"""Pin the ready canonical public promotion collection and its exact tasks."""

from .fact_fingerprint import canonical, digest
from .public_training_query import tasks

VERSION = "canonical-promotion-v1"
SHA = "2202c8c0a699779816b478ecabb7f2a8c5b206a94649f2968199def6a0aaeb75"
TASKS = "34d12d5cbbbb5189c748a6fc22d0c45ade4cff8c80d33a932b06bdbda8676e90"


def collection(db):
    row = db.connection.execute(
        """SELECT substr(source_url,1,1025),substr(source_revision,1,1025),
        substr(source_sha256,1,1025),substr(content_sha256,1,1025),substr(content_format,1,1025),
        substr(license,1,1025),substr(attribution,1,1025),substr(license_notice,1,1025),
        accepted,excluded,state FROM public_collections
        WHERE version=?""",
        (VERSION,),
    ).fetchone()
    expected = (
        "https://github.com/pavelkrotkov/chess-knowledge-coach",
        "project-authored-canonical-promotion-v1",
        SHA,
        SHA,
        "fen_csv",
        "CC0-1.0",
        "Chess Knowledge Coach project contributors",
        "Project-authored canonical exercises dedicated under CC0 1.0: https://creativecommons.org/publicdomain/zero/1.0/",
        8,
        0,
        "ready",
    )
    if row is None or tuple(row) != expected:
        raise ValueError("canonical collection unavailable")
    if db.connection.execute(
        """SELECT 1 FROM public_tasks t JOIN public_collections c ON c.id=t.collection_id
        WHERE c.version=? LIMIT 1 OFFSET 8""",
        (VERSION,),
    ).fetchone():
        raise ValueError("too many canonical tasks")
    if db.connection.execute(
        """SELECT 1 FROM public_tasks t JOIN public_collections c ON c.id=t.collection_id
        WHERE c.version=? AND (length(substr(CAST(t.lines_json AS BLOB),1,65537))>65536
        OR length(substr(CAST(t.prompt_fen AS BLOB),1,257))>256
        OR length(substr(CAST(t.task_id AS BLOB),1,257))>256) LIMIT 1""",
        (VERSION,),
    ).fetchone():
        raise ValueError("canonical tasks exceed bounds")
    rows = tasks(db, VERSION, 9)
    canonical_tasks = [
        {
            "id": item["task_id"],
            "fen": item["prompt_fen"],
            "objective": item["objective"],
            "lines": item["lines"],
        }
        for item in rows
    ]
    if len(rows) != 8 or digest(canonical(canonical_tasks)) != TASKS:
        raise ValueError("canonical tasks changed")
    return rows
