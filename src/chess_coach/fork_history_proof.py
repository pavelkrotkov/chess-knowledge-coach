"""Validate recorded fork result provenance without running another proof."""

from .capture_plan_result import _move
from .fork_assessment_miss_result import valid as valid_miss
from .objective_events import assistance
from .objective_fork_contract import MISS_OBJECTIVE, MISS_VERIFIER, OBJECTIVE, VERIFIER
from .objective_fork_owned_replay import valid as valid_owned_miss


def _bound(result, request):
    keys = (
        "objective_version",
        "history_mode",
        "snapshot_hash",
        "source_hash",
        "event_prefix_hash",
    )
    verifier = {OBJECTIVE: VERIFIER, MISS_OBJECTIVE: MISS_VERIFIER}.get(
        request["objective_version"]
    )
    return (
        verifier is not None
        and isinstance(result, dict)
        and all(result.get(key) == request[key] for key in keys)
        and result.get("verifier") == verifier
        and result.get("learning_eligible") is False
    )


def valid(result, request, events, board, move, session=None):
    if not _bound(result, request):
        return False
    if result.get("status") == "unresolved":
        return True
    return (
        (
            result.get("status") == "correct"
            or valid_miss(result, board, move, session)
            or valid_owned_miss(result, board, move, session)
        )
        and result.get("assistance") == assistance(events[:-1])
        and _move(result, board, move)
    )
