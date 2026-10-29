"""Read immutable public collection tasks with licensing provenance."""

import json

TASK_SELECT = """SELECT t.task_id,t.prompt_fen,t.objective,t.lines_json,
    c.version,c.source_url,c.source_revision,c.source_sha256,c.content_sha256,c.license,
    c.attribution,c.license_notice FROM public_tasks t JOIN public_collections c ON c.id=t.collection_id
    WHERE c.state=\u0027ready\u0027 AND c.version=?"""


def collections(db, after_version=""):
    rows = db.connection.execute(
        """SELECT version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,accepted,excluded FROM public_collections
        WHERE state=\u0027ready\u0027 AND version>? ORDER BY version LIMIT 100""",
        (after_version,),
    ).fetchall()
    return [dict(row) for row in rows]


def tasks(db, version, limit=100, after_id=""):
    if not 1 <= limit <= 100:
        raise ValueError("invalid task limit")
    rows = db.connection.execute(
        TASK_SELECT + " AND t.task_id>? ORDER BY t.task_id LIMIT ?", (version, after_id, limit)
    ).fetchall()
    return [_decode(row) for row in rows]


def task(db, version, task_id):
    row = db.connection.execute(TASK_SELECT + " AND t.task_id=?", (version, task_id)).fetchone()
    return _decode(row) if row else None


def _decode(row):
    item = dict(row)
    item["lines"] = json.loads(item.pop("lines_json"))
    return item


def library_groups(db):
    groups = collections(db)
    for group in groups:
        group["tasks"] = tasks(db, group["version"], 10)
        group["reasons"] = exclusion_reasons(db, group["version"])
    return groups


def exclusion_reasons(db, version):
    rows = db.connection.execute(
        """SELECT e.reason,COUNT(*) AS count FROM public_exclusions e
        JOIN public_collections c ON c.id=e.collection_id WHERE c.version=? AND c.state=\u0027ready\u0027
        GROUP BY e.reason ORDER BY e.reason LIMIT 20""",
        (version,),
    ).fetchall()
    return [dict(row) for row in rows]
