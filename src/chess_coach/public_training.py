"""Import licensed public direct-prompt tasks as immutable versions."""

import json

from .public_training_collect import collect
from .public_training_integrity import verify_snapshot
from .public_training_manifest import read_manifest


def import_collection(db, content, source, manifest_path, *, project_root):
    manifest, path, source_path, signatures = read_manifest(
        manifest_path, project_root, content, source
    )
    tasks, excluded = collect(path, manifest["content_format"])
    verify_snapshot((path, source_path), signatures, manifest)
    if not tasks and not excluded:
        raise ValueError("collection has no records")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        fields = (
            "version",
            "source_url",
            "source_revision",
            "source_sha256",
            "content_sha256",
            "content_format",
            "license",
            "attribution",
            "license_notice",
        )
        cursor = db.connection.execute(
            """INSERT INTO public_collections
            (version,source_url,source_revision,source_sha256,content_sha256,content_format,license,
             attribution,license_notice,accepted,excluded,state) VALUES(?,?,?,?,?,?,?,?,?,?,?,\u0027staging\u0027)""",
            (*[manifest[key] for key in fields], len(tasks), len(excluded)),
        )
        collection_id = cursor.lastrowid
        db.connection.executemany(
            "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
            [
                (
                    collection_id,
                    task["id"],
                    task["fen"],
                    task["objective"],
                    json.dumps(task["lines"]),
                )
                for task in tasks
            ],
        )
        db.connection.executemany(
            "INSERT INTO public_exclusions VALUES(?,?,?)",
            [(collection_id, number, reason) for number, reason in excluded],
        )
        db.connection.execute(
            "UPDATE public_collections SET state=\u0027ready\u0027 WHERE id=?", (collection_id,)
        )
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise
    return {"version": manifest["version"], "accepted": len(tasks), "excluded": len(excluded)}
