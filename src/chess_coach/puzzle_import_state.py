"""Create, resume and report versioned corpus import state."""

import json

from .db import Database

IMPORTER_VERSION = "corpus-csv-v1"


def initialize(
    db: Database,
    version: str,
    path: str,
    digest: str,
    archive: str | None,
    source_url: str | None,
    fields: list[str],
    start: int,
    selection: str | None,
) -> int:
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        old = db.connection.execute(
            """SELECT c.id,c.state,c.checksum,i.csv_path,i.csv_sha256,i.archive_sha256,
            i.source_url,i.importer_version,i.header_json,i.selection_json
            FROM puzzle_corpora c LEFT JOIN puzzle_imports i ON i.corpus_id=c.id WHERE c.version=?""",
            (version,),
        ).fetchone()
        if old is None:
            cursor = db.connection.execute(
                "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES (?,?,?,'staging')",
                (version, source_url or "local-decoded-csv", digest),
            )
            corpus_id = cursor.lastrowid
            if corpus_id is None:
                raise RuntimeError("SQLite did not return a corpus ID")
            db.connection.execute(
                """INSERT INTO puzzle_imports
                (corpus_id,csv_path,csv_sha256,archive_sha256,source_url,importer_version,header_json,byte_offset,selection_json)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    corpus_id,
                    path,
                    digest,
                    archive,
                    source_url,
                    IMPORTER_VERSION,
                    json.dumps(fields),
                    start,
                    selection,
                ),
            )
        else:
            corpus_id = _resume(db, old, path, digest, archive, source_url, fields, selection)
        db.connection.commit()
        return int(corpus_id)
    except BaseException:
        db.connection.rollback()
        raise


def _resume(db: Database, old, path, digest, archive, source_url, fields, selection):
    expected = (path, digest, archive, source_url, IMPORTER_VERSION, json.dumps(fields), selection)
    actual = tuple(
        old[key]
        for key in (
            "csv_path",
            "csv_sha256",
            "archive_sha256",
            "source_url",
            "importer_version",
            "header_json",
            "selection_json",
        )
    )
    if old["checksum"] != digest or actual != expected or old["state"] == "legacy_ready":
        raise ValueError("corpus version already has a different source or import identity")
    if old["state"] == "failed":
        db.connection.execute("UPDATE puzzle_corpora SET state='staging' WHERE id=?", (old["id"],))
        db.connection.execute(
            "UPDATE puzzle_imports SET error=NULL WHERE corpus_id=?", (old["id"],)
        )
    return old["id"]
