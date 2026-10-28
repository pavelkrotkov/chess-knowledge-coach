"""Compose one bounded continuation page of a daily plan."""

from datetime import datetime

from .curriculum_cursor_codec import encode_cursor
from .curriculum_due_scan import scan_due
from .curriculum_evidence import evidence_summary
from .curriculum_new_page import new_page
from .curriculum_query import corpus_status
from .db import Database


def build_page(db: Database, state: dict, learner: str, now: datetime) -> dict:
    summary = evidence_summary(db, learner, now, state["scan_limit"])
    status, invalid_ratings = corpus_status(db, state["corpus_version"])
    items = []
    scan = {
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
    reason = None
    if state["phase"] == "due":
        items, scan["due_examined"], scan["due_incomplete"] = scan_due(db, state, now, summary)
        if scan["due_incomplete"] and len(state["seen"]) < state["limit"]:
            reason = "due_scan_incomplete"
    if _should_scan_new(state, reason):
        new_items, status, reason = new_page(db, state, summary, scan, status)
        items.extend(new_items)
    elif status == "available":
        status = "not_scanned"
    return {
        "as_of": now.isoformat(),
        "evidence": summary,
        "corpus_status": status,
        "scan": scan,
        "items": items,
        "next_cursor": _next_cursor(db, state, reason),
        "continuation_reason": reason,
        "diagnostic": _diagnostic(reason),
    }


def _should_scan_new(state: dict, reason: str | None) -> bool:
    return reason is None and len(state["seen"]) < state["limit"] and state["phase"] == "new"


def _next_cursor(db: Database, state: dict, reason: str | None) -> str | None:
    return encode_cursor(db, state) if reason and reason.endswith("_scan_incomplete") else None


def _diagnostic(reason: str | None) -> str | None:
    if reason == "scheduled_prompt_unavailable":
        return "Restore the referenced versioned corpus or repair the scheduled item source."
    return None
