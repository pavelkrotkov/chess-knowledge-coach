"""Identify only the exact owner-bound canonical immediate-promotion policy."""

import json

from .learner_identity import normalize_identity
from .objective_contract import STANDALONE
from .objective_promotion_contract import NOW
from .objective_promotion_contract import VERSION as OBJECTIVE_VERSION
from .plan_promotion_catalog import VERSION, collection
from .unified_training_item import source_ref

SOURCE = "unified_canonical_promotion"


def is_source(row):
    if (row["source_type"], row["source_version"], row["objective"]) != ("public", VERSION, NOW):
        return False
    data = json.loads(row["provenance_json"])
    return (
        data.get("objective_version") == OBJECTIVE_VERSION
        and data.get("history_mode") == STANDALONE
        and not any(key.startswith("related_") for key in data)
    )


def binding(db, row):
    if db.compat32 or not is_source(row):
        return None
    collection(db)
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
        "promotion",
        "execute",
    ):
        return None
    return item
