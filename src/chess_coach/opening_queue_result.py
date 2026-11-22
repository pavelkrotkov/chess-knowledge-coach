"""Read only bounded, source-bound immutable comparison results."""

from .opening_measure_prepare import V2
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
    reference = item["configuration"].get("purpose_policy") == V2
    if reference and (
        outcome.get("effective_multipv") != item["configuration"].get("multipv")
        or outcome.get("work", {}).get("requested_nodes")
        != item["configuration"].get("requested_nodes")
    ):
        raise ValueError("comparison configuration differs")
    if not complete(outcome, item["source"], board, reference=reference):
        raise ValueError("comparison result is incomplete")
    return outcome
