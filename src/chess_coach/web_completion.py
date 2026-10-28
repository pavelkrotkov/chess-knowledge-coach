"""Read persisted completion feedback and the current review schedule."""

import json

from .db import Database


def completion(db: Database, attempt: str, item_id: int) -> dict | None:
    row = db.connection.execute(
        """SELECT c.response_json, i.due FROM training_completions c
        JOIN training_items i ON i.id=? WHERE c.attempt_id=?""",
        (item_id, attempt),
    ).fetchone()
    if row is None:
        return None
    response = json.loads(row["response_json"])
    return {
        "reason": response["training"]["evidence_reason"],
        "due": row["due"],
        "evidence_id": response["training"]["evidence_id"],
    }
