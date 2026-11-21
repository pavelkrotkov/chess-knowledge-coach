"""Bind newly created corpus mate attempts to an owner-specific review item."""

from .learner_identity import normalize_identity
from .unified_corpus_mate import GOAL, is_source
from .unified_session_state import now
from .unified_training_item import existing, training_item
from .unified_training_owned_capture import SOURCE as CAPTURE_SOURCE
from .unified_training_owned_capture import is_source as capture_source


def enroll(db, row, *, training, item_id, created, goal):
    if db.compat32:
        raise ValueError("new qualified mate training is unavailable")
    if existing(db, row, training, item_id):
        return
    capture = _capture_policy(row, goal, training, created)
    subject = normalize_identity(row["subject"])
    if subject is None:
        raise ValueError("training requires a learner identity")
    item_id = (
        training_item(db, row, item_id, source=CAPTURE_SOURCE, skill="hanging_piece")
        if capture
        else training_item(db, row, item_id)
    )
    db.connection.execute(
        "INSERT INTO unified_training_enrollments VALUES(?,?,?,?)",
        (row["attempt_id"], item_id, subject, now()),
    )


def enroll_if_requested(db, row, *, training, item_id, created, goal):
    if training or item_id is not None:
        enroll(db, row, training=training, item_id=item_id, created=created, goal=goal)


def _capture_policy(row, goal, training, created):
    if not training or not created:
        raise ValueError("new qualified training is unavailable")
    if goal is None and capture_source(row):
        return True
    if goal == GOAL and is_source(row):
        return False
    raise ValueError("new qualified training is unavailable")
