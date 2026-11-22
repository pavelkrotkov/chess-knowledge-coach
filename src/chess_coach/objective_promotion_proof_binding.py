"""Bind stored promotion proof to its source, event and board."""

from .objective_events import assistance
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


def immediate(request, result, board, move):
    binding(request, result, board, move)
    status = "correct" if move.promotion else "incorrect"
    reason = "promotion_performed" if move.promotion else "not_immediate_promotion"
    if result.get("status") != status or result.get("reason") != reason:
        raise ValueError("canonical promotion outcome unavailable")
    return status


def attempt(events, result, observed, hints):
    if (
        observed["outcome"] != "unresolved"
        or assistance(events[:-1]) != result.get("assistance")
        or observed["hints"] != hints
    ):
        raise ValueError("canonical promotion assistance unavailable")
