"""Read bounded corpus progress and theme coverage."""

import json

from .db import Database


def corpus_report(db: Database) -> list[dict]:
    rows = db.connection.execute(
        """SELECT c.id,c.version,c.state,c.source,c.checksum,c.imported_rows,
        i.csv_sha256,i.archive_sha256,i.importer_version,i.byte_offset,i.row_number,
        i.accepted,i.rejected,i.error,i.selection_json FROM puzzle_corpora c
        LEFT JOIN puzzle_imports i ON i.corpus_id=c.id ORDER BY c.version"""
    ).fetchall()
    return [_report(db, row) for row in rows]


def _report(db: Database, row) -> dict:
    result = dict(row)
    selection = result.pop("selection_json")
    result["selection"] = json.loads(selection) if selection is not None else None
    if result["state"] == "legacy_ready":
        result["source"] = "legacy local import"
    themes = db.connection.execute(
        "SELECT theme,count FROM puzzle_theme_counts WHERE corpus_id=? ORDER BY theme LIMIT 201",
        (row["id"],),
    ).fetchall()
    result["themes"] = {item["theme"]: item["count"] for item in themes[:200]}
    result["themes_truncated"] = len(themes) > 200
    result["rejections"] = [
        {
            "puzzle_id": item["puzzle_id"],
            "record_number": item["record_number"],
            "reason": "invalid position or illegal solution",
        }
        for item in db.connection.execute(
            "SELECT puzzle_id,record_number FROM puzzle_import_seen WHERE corpus_id=? AND valid=0 ORDER BY record_number LIMIT 20",
            (row["id"],),
        )
    ]
    result["rejected_reason"] = (
        "invalid position or illegal solution" if result["rejected"] else None
    )
    result.pop("id")
    return result


def report_one(db: Database, corpus_id: int) -> dict:
    version = db.connection.execute(
        "SELECT version FROM puzzle_corpora WHERE id=?", (corpus_id,)
    ).fetchone()[0]
    return next(item for item in corpus_report(db) if item["version"] == version)
