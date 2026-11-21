"""Report progress through a bounded new-puzzle scan."""

import sqlite3

from .curriculum_new_scan import scan_new
from .db import Database
from .tactical_course_budget import PreviewUnavailable


def new_page(
    db: Database, state: dict, summary: dict, scan: dict, status: str, *, check=None, quota=None
):
    if status != "available":
        return [], status, None
    items, counts, reason = scan_new(
        db,
        state,
        summary,
        scan["scheduled_examined"],
        check=check,
        quota=quota,
        corpus_examined=scan["corpus_examined"],
    )
    scan.update(counts)
    scan["corpus_incomplete"] = reason == "corpus_scan_incomplete"
    scan["scheduled_incomplete"] = reason == "scheduled_scan_incomplete"
    scan["scheduled_unavailable"] = reason == "scheduled_prompt_unavailable"
    if reason == "family_quota_complete":
        return items, "scanned", reason
    if reason == "corpus_scan_incomplete":
        return items, "scan_incomplete", reason
    if reason == "scheduled_scan_incomplete":
        return items, "scheduled_scan_incomplete", reason
    if reason == "scheduled_prompt_unavailable":
        return items, "scheduled_prompt_unavailable", reason
    return items, "scanned" if items else "no_new_candidates", None


def diagnostic(reason: str | None) -> str | None:
    if reason == "scheduled_prompt_unavailable":
        return "Restore the referenced versioned corpus or repair the scheduled item source."
    return None


def checked_page(db, state, summary, counts, corpus, check):
    # Keep the pending candidate when a scheduled-source proof is interrupted.
    working, work_counts = dict(state), dict(counts)
    try:
        items, status, reason = new_page(
            db,
            working,
            summary,
            work_counts,
            corpus,
            check=check,
            quota=1,
        )
    except (PreviewUnavailable, sqlite3.OperationalError):
        state["pending"] = working["pending"]
        state["scheduled_after"] = working["scheduled_after"]
        state["new_after"] = working["new_after"]
        raise
    state.update(working)
    counts.update(work_counts)
    return items, status, reason, None
