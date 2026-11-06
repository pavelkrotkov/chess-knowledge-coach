"""Read only bounded, source-bound immutable comparison results."""

from .opening_queue_artifact import load
from .opening_queue_failure import exists
from .opening_queue_proof import complete


def result(directory, item, board):
    payload = load(directory, item)
    if payload is None:
        return {"status": "unavailable"} if exists(directory, item) else None
    outcome = payload["result"]
    if outcome["status"] == "insufficient":
        return {"status": "unavailable", "reason": outcome.get("reason")}
    if not complete(outcome, item["source"], board):
        raise ValueError("comparison result is incomplete")
    return outcome
