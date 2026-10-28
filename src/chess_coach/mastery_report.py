"""Recompute current heuristic estimates when they are requested."""

from datetime import datetime
from typing import Any

from .db import Database
from .mapping_transaction import mapping_transaction
from .mastery_time import as_utc


def mastery_report(
    db: Database, *, subject: str = "default", as_of: datetime | None = None
) -> list[dict[str, Any]]:
    from .mastery import update_mastery

    subject = subject.strip().casefold()
    now = as_utc(as_of)
    with mapping_transaction(db):
        rows = db.connection.execute(
            """SELECT skill, operation FROM evidence_mappings WHERE subject = ?
            UNION SELECT skill, operation FROM mastery_states WHERE subject = ?
            ORDER BY skill, operation""",
            (subject, subject),
        ).fetchall()
        return [
            update_mastery(
                db, subject=subject, skill=row["skill"], operation=row["operation"], as_of=now
            )
            for row in rows
        ]
