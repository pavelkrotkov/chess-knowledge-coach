"""Advance the original material archive cursor under the remaining budget."""

import sqlite3

from .material_worker_cursor import advance, scan
from .material_worker_item import process_item


def work(db, config, report, outcomes, exclude):
    limit = config.material_max_scan - report["examined"]
    key, rows = scan(db, config.learner, limit)
    examined = 0
    for row in rows[:limit]:
        if report["processed"] >= config.material_max_decisions:
            report["capped"] = True
            break
        examined += 1
        report["examined"] += 1
        if row["id"] not in exclude:
            process_item(db, row["id"], config.learner, report, outcomes)
        if not _advance(db, key, row["id"]):
            report.update(capped=True, detail="cursor_busy")
            break
    if len(rows) > limit and examined == limit:
        report["capped"] = True


def _advance(db, key, position_id):
    try:
        advance(db, key, position_id)
        return True
    except sqlite3.OperationalError as error:
        if getattr(error, "sqlite_errorcode", 0) & 255 != sqlite3.SQLITE_BUSY:
            raise
        return False
