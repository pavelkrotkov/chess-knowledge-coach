"""Finish a verified puzzle, evidence and FSRS review in one transaction."""

from .db import Database
from .puzzle_session_events import apply_event_in_transaction
from .puzzle_session_state import _session
from .training_feedback_finish import complete_feedback
from .training_feedback_item import puzzle_training_ref as puzzle_training_ref
from .training_feedback_item import training_item
from .training_feedback_request import validate_request
from .training_feedback_storage import previous_completion
from .training_transaction import training_transaction


def submit_training_move(
    db: Database,
    attempt_id: str,
    *,
    event_id: str,
    move: str,
    item_id: int,
    subject: str,
) -> dict:
    normalized, request_hash = validate_request(attempt_id, event_id, move, item_id, subject)
    with training_transaction(db):
        previous = previous_completion(db, attempt_id, request_hash)
        if previous is not None:
            return previous
        session = _session(db, attempt_id)
        if session["status"] != "active":
            raise ValueError("puzzle attempt is already complete without training feedback")
        item = training_item(db, item_id, session)
        result = apply_event_in_transaction(db, attempt_id, event_id, "move", move)
        if result["status"] == "active":
            return result
        return complete_feedback(db, session, item, result, move, normalized, request_hash)
