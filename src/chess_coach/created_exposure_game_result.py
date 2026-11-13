"""Check a created-exposure result against its immutable request and first answer."""

from .capture_plan_result import _move
from .objective_created_contract import OBJECTIVE, VERIFIER
from .objective_events import assistance
from .objective_provenance import SECONDS


def _outcome(result, board, move, target):
    if result.get("status") == "correct":
        return result.get("reason") == "no_profitable_immediate_capture"
    if (result.get("status"), result.get("reason")) != ("incorrect", "profitable_capture"):
        return False
    after = board.copy()
    after.push(move)
    reply = after.parse_uci(result["capture_reply"])
    return after.is_capture(reply) and reply.to_square == (
        move.to_square if move.from_square == target else target
    )


# A verified answer must be tied to the same immutable request and event prefix.
# Assistance or a learning-eligible result cannot count as an independent answer.
def _bound(result, request, events, observed):
    keys = (
        "objective_version",
        "history_mode",
        "snapshot_hash",
        "source_hash",
        "event_prefix_hash",
    )
    return (
        request["objective_version"] == OBJECTIVE
        and all(result.get(key) == request[key] for key in keys)
        and result.get("verifier") == VERIFIER
        and result.get("learning_eligible") is False
        and result.get("assistance") == assistance(events[:-1]) == "unassisted"
        and observed["hints"] == observed["reveals"] == 0
    )


def _limits(result):
    limits = result.get("limits", {})
    seconds = limits.get("compute_timeout_seconds")
    return limits.get("plies") == 3 and type(seconds) in {int, float} and 0 < seconds <= SECONDS


def valid(result, request, events, board, move, target, observed):
    return (
        _bound(result, request, events, observed)
        and _limits(result)
        and _move(result, board, move)
        and _outcome(result, board, move, target)
    )
