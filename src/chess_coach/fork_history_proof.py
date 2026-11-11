"""Validate recorded fork result provenance without running another proof."""

from .capture_plan_result import _move
from .fork_assessment_miss_result import valid as valid_miss
from .objective_events import assistance
from .objective_fork_contract import VERIFIER


def _bound(result, request):
    keys = (
        "objective_version",
        "history_mode",
        "snapshot_hash",
        "source_hash",
        "event_prefix_hash",
    )
    return (
        isinstance(result, dict)
        and all(result.get(key) == request[key] for key in keys)
        and result.get("verifier") == VERIFIER
        and result.get("learning_eligible") is False
    )


def valid(result, request, events, board, move, session=None):
    if not _bound(result, request):
        return False
    if result.get("status") == "unresolved":
        return True
    return (
        (result.get("status") == "correct" or valid_miss(result, board, move, session))
        and result.get("assistance") == assistance(events[:-1])
        and _move(result, board, move)
    )
