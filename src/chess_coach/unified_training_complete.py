"""Complete an enrolled corpus mate attempt in one independent transaction."""

import json

from .learner_identity import normalize_identity
from .training_feedback_request import validate_request
from .training_review import review_item_in_transaction
from .training_transaction import training_transaction
from .unified_corpus_mate import is_source
from .unified_session_state import session_row
from .unified_source_current import require_current
from .unified_training_item import SOURCE, source_ref
from .unified_training_receipt import save
from .unified_training_terminal import terminal


def _enrollment(db, row):
    item = db.connection.execute(
        """SELECT e.item_id,e.subject,i.source_type,i.source_ref,i.skill,i.operation
        FROM unified_training_enrollments e JOIN training_items i ON i.id=e.item_id
        WHERE e.attempt_id=?""",
        (row["attempt_id"],),
    ).fetchone()
    expected = source_ref(
        row["subject"], row["source_version"], row["source_key"], row["snapshot_hash"]
    )
    if item is None:
        return None
    if (
        item["subject"],
        item["source_type"],
        item["source_ref"],
        item["skill"],
        item["operation"],
    ) != (normalize_identity(row["subject"]), SOURCE, expected, "mate_in_one", "execute"):
        raise ValueError("training source is unavailable")
    return item


def complete(db, attempt_id, subject, *, event_id=None):
    if db.compat32:
        raise ValueError("learning is unavailable in compatibility mode")
    row = session_row(db, attempt_id, subject)
    from .unified_training_dispatch import policy

    selected = policy(row)
    if selected is not None:
        from .unified_capture_completion import complete as complete_policy

        return complete_policy(db, attempt_id, subject, event_id=event_id, policy=selected)
    with training_transaction(db):
        row = session_row(db, attempt_id, subject)
        if not is_source(row):
            raise ValueError("qualified mate source required")
        require_current(db, row)
        item = _enrollment(db, row)
        if item is None:
            raise ValueError("attempt is not enrolled for learning")
        event, fact, assisted = terminal(db, row, event_id)
        _, request_hash = validate_request(
            attempt_id, event["event_id"], event["submitted_move"], item["item_id"], subject
        )
        previous = db.connection.execute(
            "SELECT request_hash,response_json FROM unified_training_completions WHERE attempt_id=?",
            (attempt_id,),
        ).fetchone()
        if previous:
            if previous["request_hash"] != request_hash:
                raise ValueError("completion conflicts with the recorded request")
            return json.loads(previous["response_json"])
        return save(db, row, item, event, fact, assisted, request_hash, review_item_in_transaction)
