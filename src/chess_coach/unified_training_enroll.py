"""Bind newly created corpus mate attempts to an owner-specific review item."""

from .learner_identity import normalize_identity
from .unified_session_state import now
from .unified_training_enroll_policy import policy
from .unified_training_item import existing, training_item


def enroll(db, row, *, training, item_id, created, goal):
    if db.compat32:
        raise ValueError("new qualified mate training is unavailable")
    if existing(db, row, training, item_id):
        return
    source, skill = policy(row, goal, training, created)
    subject = normalize_identity(row["subject"])
    if subject is None:
        raise ValueError("training requires a learner identity")
    item_id = (
        training_item(db, row, item_id, source=source, skill=skill)
        if source
        else training_item(db, row, item_id)
    )
    db.connection.execute(
        "INSERT INTO unified_training_enrollments VALUES(?,?,?,?)",
        (row["attempt_id"], item_id, subject, now()),
    )


def enroll_if_requested(db, row, *, training, item_id, created, goal):
    if training or item_id is not None:
        enroll(db, row, training=training, item_id=item_id, created=created, goal=goal)
