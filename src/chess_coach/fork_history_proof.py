"""Validate recorded fork result provenance without running another proof."""

from .fork_history_witness import correct
from .objective_fork_contract import VERIFIER


def valid(result, request, events, board, move, row):
    keys = (
        "objective_version",
        "history_mode",
        "snapshot_hash",
        "source_hash",
        "event_prefix_hash",
    )
    if (
        not isinstance(result, dict)
        or any(result.get(key) != request[key] for key in keys)
        or result.get("verifier") != VERIFIER
        or result.get("learning_eligible") is not False
    ):
        return False
    if result.get("status") == "unresolved":
        return True
    return correct(result, events, board, move, row)
