"""Bounded plan-scan counters and continuation decisions."""

from .curriculum_cursor_codec import encode_cursor
from .db import Database


def initial_scan(invalid_ratings):
    return {
        "due_examined": 0,
        "due_incomplete": False,
        "corpus_examined": 0,
        "corpus_incomplete": False,
        "scheduled_examined": 0,
        "scheduled_incomplete": False,
        "scheduled_unavailable": False,
        "scheduled_unavailable_item_id": None,
        "invalid_ratings_present": invalid_ratings,
    }


def should_scan_new(state: dict, reason: str | None) -> bool:
    return reason is None and len(state["seen"]) < state["limit"] and state["phase"] == "new"


def next_cursor(db: Database, state: dict, reason: str | None) -> str | None:
    return encode_cursor(db, state) if reason and reason.endswith("_scan_incomplete") else None


def should_scan_capture(state, reason):
    return reason is None and state["phase"] == "capture" and len(state["seen"]) < state["limit"]


def capture_generation(budget, status):
    return budget.version if budget is not None and status is not None else None
