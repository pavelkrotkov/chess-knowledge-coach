"""Compose one bounded continuation page of a daily plan."""

from datetime import datetime

from .curriculum_due_scan import scan_due
from .curriculum_evidence import evidence_summary
from .curriculum_new_capture import scan as scan_capture
from .curriculum_new_page import diagnostic, new_page
from .curriculum_page_state import (
    capture_generation,
    initial_scan,
    next_cursor,
    should_scan_capture,
    should_scan_new,
)
from .curriculum_query import corpus_status
from .db import Database


def build_page(db: Database, state: dict, learner: str, now: datetime, budget=None) -> dict:
    summary = evidence_summary(db, learner, now, state["scan_limit"])
    status, invalid_ratings = corpus_status(db, state["corpus_version"])
    items = []
    scan = initial_scan(invalid_ratings)
    reason = None
    if state["phase"] == "due":
        items, scan["due_examined"], scan["due_incomplete"], reason = scan_due(
            db, state, now, summary, scan
        )
        if reason is None and scan["due_incomplete"] and len(state["seen"]) < state["limit"]:
            reason = "due_scan_incomplete"
    capture_status = capture_focus = None
    if should_scan_capture(state, reason):
        capture_items, capture_status, reason, capture_focus = scan_capture(
            db, state, learner, scan, budget
        )
        items.extend(capture_items)
    if should_scan_new(state, reason):
        new_items, status, reason = new_page(db, state, summary, scan, status)
        items.extend(new_items)
    elif status == "available":
        status = "not_scanned"
    return {
        "as_of": now.isoformat(),
        "evidence": summary,
        "corpus_status": status,
        "capture_status": capture_status,
        "capture_focus": capture_focus,
        "capture_generation": capture_generation(budget, capture_status),
        "scan": scan,
        "items": items,
        "next_cursor": next_cursor(db, state, reason),
        "continuation_reason": reason,
        "diagnostic": diagnostic(reason),
    }
