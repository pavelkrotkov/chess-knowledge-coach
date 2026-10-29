"""Bind stored promotion proof to its source, event and board."""

from .objective_promotion_contract import VERIFIER
from .objective_short_history import history_hash


def binding(row, result, board, move):
    fields = (
        "objective_version",
        "history_mode",
        "snapshot_hash",
        "event_prefix_hash",
        "source_hash",
    )
    if any(result.get(field) != row[field] for field in fields):
        raise ValueError("promotion proof binding changed")
    if result.get("verifier") != VERIFIER or result.get("history_hash") != history_hash(board):
        raise ValueError("promotion proof history changed")
    if result.get("move") != move.uci():
        raise ValueError("promotion proof move changed")
