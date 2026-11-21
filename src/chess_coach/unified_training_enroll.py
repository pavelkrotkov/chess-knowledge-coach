"""Bind newly created corpus mate attempts to an owner-specific review item."""

from .learner_identity import normalize_identity
from .unified_corpus_mate import GOAL, is_source
from .unified_session_state import now
from .unified_training_item import training_item


def _existing(db, row, training, item_id):
    existing = db.connection.execute(
        "SELECT item_id FROM unified_training_enrollments WHERE attempt_id=?", (row["attempt_id"],)
    ).fetchone()
    if existing is None:
        return False
    if not training or (item_id is not None and item_id != existing[0]):
        raise ValueError("attempt belongs to another training request")
    return True


def enroll(db, row, *, training, item_id, created, goal):
    if db.compat32:
        raise ValueError("new qualified mate training is unavailable")
    if _existing(db, row, training, item_id):
        return
    if not training or not created or goal != GOAL or not is_source(row):
        raise ValueError("new qualified mate training is unavailable")
    subject = normalize_identity(row["subject"])
    if subject is None:
        raise ValueError("training requires a learner identity")
    item_id = training_item(db, row, item_id)
    db.connection.execute(
        "INSERT INTO unified_training_enrollments VALUES(?,?,?,?)",
        (row["attempt_id"], item_id, subject, now()),
    )


def enroll_if_requested(db, row, *, training, item_id, created, goal):
    if training or item_id is not None:
        enroll(db, row, training=training, item_id=item_id, created=created, goal=goal)
