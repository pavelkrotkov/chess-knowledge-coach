"""Replay the exact enrolled public standalone immediate-mate attempt."""

from .mate_assessment_events import replay
from .training_feedback_request import validate_request
from .unified_fork_learning_events import answer
from .unified_training_proof import proof as mate_proof
from .unified_training_public_mate import SOURCE as SOURCE
from .unified_training_public_mate import binding

SKILL = "mate_in_one"
POLICY = "unified-public-standalone-mate-schedule-v1"
MAPPER = "unified-public-standalone-mate-evidence-v1"


def proof(db, row, event_id=None):
    item = binding(db, row)
    if item is None:
        raise ValueError("public mate enrollment unavailable")
    observed = replay(db, row)
    event = answer(db, row, event_id)
    fact = mate_proof(row, event)
    expected = "verified" if fact["played_checkmate"] else "incorrect"
    if observed["outcome"] != expected or row["next_index"] != 1 or not row["finished_at"]:
        raise ValueError("public mate terminal history unavailable")
    fact["status"] = "correct" if fact["played_checkmate"] else "incorrect"
    fact["verifier"] = "public-mate-legal-v1"
    fact["history"] = "standalone_fresh"
    _, fingerprint = validate_request(
        row["attempt_id"],
        event["event_id"],
        event["submitted_move"],
        item["item_id"],
        row["subject"],
    )
    return item, event, fact, bool(observed["hints"]), fingerprint
