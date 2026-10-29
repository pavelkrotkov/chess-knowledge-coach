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
) -> int:
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        old = db.connection.execute(
            """SELECT c.id,c.state,c.checksum,i.csv_path,i.csv_sha256,i.archive_sha256,
            i.source_url,i.importer_version,i.header_json
            FROM puzzle_corpora c LEFT JOIN puzzle_imports i ON i.corpus_id=c.id WHERE c.version=?""",
            (version,),
        ).fetchone()
        if old is None:
            cursor = db.connection.execute(
                "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES (?,?,?,'staging')",
                (version, source_url or "local-decoded-csv", digest),
            )
            corpus_id = cursor.lastrowid
            db.connection.execute(
                """INSERT INTO puzzle_imports
                (corpus_id,csv_path,csv_sha256,archive_sha256,source_url,importer_version,header_json,byte_offset)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    corpus_id,
                    path,
                    digest,
                    archive,
                    source_url,
                    IMPORTER_VERSION,
                    json.dumps(fields),
                    start,
                ),
            )
        else:
            corpus_id = _resume(db, old, path, digest, archive, source_url, fields)
        db.connection.commit()
        return int(corpus_id)
    except BaseException:
        db.connection.rollback()
        raise


def _resume(db: Database, old, path, digest, archive, source_url, fields):
    expected = (path, digest, archive, source_url, IMPORTER_VERSION, json.dumps(fields))
    actual = tuple(
        old[key]
        for key in (
            "csv_path",
            "csv_sha256",
            "archive_sha256",
            "source_url",
            "importer_version",
            "header_json",
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


def fail(db: Database, corpus_id: int, reason: str) -> None:
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        db.connection.execute(
            "UPDATE puzzle_corpora SET state='failed' WHERE id=? AND state='staging'", (corpus_id,)
        )
        db.connection.execute(
            "UPDATE puzzle_imports SET error=? WHERE corpus_id=?", (reason, corpus_id)
        )
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise


def corpus_report(db: Database) -> list[dict]:
    rows = db.connection.execute(
        """SELECT c.id,c.version,c.state,c.source,c.checksum,c.imported_rows,
        i.csv_sha256,i.archive_sha256,i.importer_version,i.byte_offset,i.row_number,
        i.accepted,i.rejected,i.error FROM puzzle_corpora c
        LEFT JOIN puzzle_imports i ON i.corpus_id=c.id ORDER BY c.version"""
    ).fetchall()
    return [_report(db, row) for row in rows]


def _report(db: Database, row) -> dict:
    result = dict(row)
    result["themes"] = {
        item["theme"]: item["count"]
        for item in db.connection.execute(
            "SELECT theme,count FROM puzzle_theme_counts WHERE corpus_id=? ORDER BY theme",
            (row["id"],),
        )
    }
    result["rejected_reason"] = (
        "invalid position or illegal solution" if result["rejected"] else None
    )
    result.pop("id")
    return result
