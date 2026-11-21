"""Identify only explicitly enrolled owned named-target capture attempts."""

import json

from .learner_identity import normalize_identity
from .objective_capture_contract import TARGET_OBJECTIVE, TARGET_VERSION
from .objective_contract import OWNED_HISTORY
from .unified_training_item import source_ref

SOURCE = "unified_owned_capture"


def is_source(row):
    if (row["source_type"], row["source_version"], row["objective"]) != (
        "own-game",
        TARGET_VERSION,
        "capture_named_target",
    ):
        return False
    data = json.loads(row["provenance_json"])
    return (
        data.get("objective_version") == TARGET_OBJECTIVE
        and data.get("history_mode") == OWNED_HISTORY
        and data.get("capture_objective") == "capture_named_target"
        and data.get("gain_threshold") == 3
    )


def enrolled(db, row):
    if db.compat32 or row["next_index"] != 0 or not is_source(row):
        return False
    item = db.connection.execute(
        """SELECT e.subject,i.source_type,i.source_ref,i.skill,i.operation
        FROM unified_training_enrollments e JOIN training_items i ON i.id=e.item_id
        WHERE e.attempt_id=?""",
        (row["attempt_id"],),
    ).fetchone()
    expected = source_ref(
        row["subject"], row["source_version"], row["source_key"], row["snapshot_hash"]
    )
    return item is not None and tuple(item) == (
        normalize_identity(row["subject"]),
        SOURCE,
        expected,
        "hanging_piece",
        "execute",
    )
