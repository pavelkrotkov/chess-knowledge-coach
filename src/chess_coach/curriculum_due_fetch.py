"""Merge bounded due pages for existing and owned-capture items."""

from datetime import datetime

from .curriculum_canonical_promotion_due import promotion_rows
from .curriculum_capture_due import capture_rows
from .curriculum_fork_due import fork_rows
from .curriculum_public_mate_due import public_rows


def fetch(
    db,
    now: datetime,
    extra: str,
    values: list,
    limit: int,
    *,
    order: str = "julianday(due),id",
):
    index = "idx_curriculum_due" if db.compat32 else "idx_curriculum_unified_due"
    source = (
        "source_type='puzzle'" if db.compat32 else "source_type IN ('puzzle','unified_corpus_m1')"
    )
    query = f"""SELECT id,source_type,source_ref,due,julianday(due) AS due_order
        FROM training_items INDEXED BY {index}
        WHERE {source} AND skill='mate_in_one' AND operation='execute'
        AND lower(due) != 'now' AND julianday(due) <= julianday(?)"""
    query += extra + f" ORDER BY {order} LIMIT ?"
    rows = list(db.connection.execute(query, [now.isoformat(), *values, limit]).fetchall())
    if db.compat32:
        return rows
    rows.extend(capture_rows(db, now, extra, values, limit, order))
    rows.extend(fork_rows(db, now, extra, values, limit, order))
    rows.extend(public_rows(db, now, extra, values, limit, order))
    rows.extend(promotion_rows(db, now, extra, values, limit, order))
    rows.extend(promotion_rows(db, now, extra, values, limit, order, forced=True))
    key = (lambda row: row["id"]) if order == "id" else (lambda row: (row["due_order"], row["id"]))
    return sorted(rows, key=key)[:limit]
