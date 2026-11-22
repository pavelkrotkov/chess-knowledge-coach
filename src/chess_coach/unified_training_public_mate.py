"""Identify exact owner-bound public standalone mate enrollment."""

from .learner_identity import normalize_identity
from .public_training_source import mate as is_source
from .unified_training_item import source_ref

SOURCE = "unified_public_m1"


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
        "mate_in_one",
        "execute",
    ):
        return None
    return item
