"""Start one signed legacy plan offer and its training item atomically."""

from .curriculum_window_offer_check import check, valid_time
from .puzzle_sessions import _create_attempt
from .training import create_training_item
from .training_feedback import puzzle_training_ref
from .training_transaction import training_transaction


def start(db, subject, version, puzzle_id, attempt_id, token):
    with training_transaction(db):
        data = check(db, token, subject, "corpus", version, puzzle_id, "legacy")
        item_id = create_training_item(
            db,
            source_type="puzzle",
            source_ref=puzzle_training_ref(version, puzzle_id),
            skill="mate_in_one",
            operation="execute",
        )
        result = _create_attempt(db, attempt_id, version, puzzle_id)
        valid_time(data)
        return item_id, result
