"""Identify the exact enrolled owned fork execution policy."""

import json

from .learner_identity import normalize_identity
from .objective_contract import OWNED_HISTORY
from .objective_fork_contract import GOAL, MISS_OBJECTIVE, is_miss_source
from .unified_training_item import source_ref

SOURCE = "unified_owned_fork"


def is_source(row):
    if not is_miss_source(row):
        return False
    data = json.loads(row["provenance_json"])
    return (
        data.get("objective_version") == MISS_OBJECTIVE
        and data.get("history_mode") == OWNED_HISTORY
        and data.get("gain_threshold") == 3
        and bool(data.get("fork_attacker"))
        and bool(data.get("fork_anchor"))
        and row["objective"] == GOAL
    )


def binding(db, row):
    if db.compat32 or not is_source(row):
        return None
    item = db.connection.execute(
        """SELECT e.subject,i.source_type,i.source_ref,i.skill,i.operation,e.item_id
        FROM unified_training_enrollments e JOIN training_items i ON i.id=e.item_id
        WHERE e.attempt_id=?""",
        (row["attempt_id"],),
    ).fetchone()
    expected = source_ref(
        row["subject"], row["source_version"], row["source_key"], row["snapshot_hash"]
    )
    if item is None or tuple(item)[:5] != (
        normalize_identity(row["subject"]),
        SOURCE,
        expected,
        "fork",
        "execute",
    ):
        return None
    return item
