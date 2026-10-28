"""Report progress through a bounded new-puzzle scan."""

from .curriculum_new_scan import scan_new
from .db import Database


def new_page(db: Database, state: dict, summary: dict, scan: dict, status: str):
    if status != "available":
        return [], status, None
    items, counts, reason = scan_new(db, state, summary, scan["scheduled_examined"])
    scan.update(counts)
    scan["corpus_incomplete"] = reason == "corpus_scan_incomplete"
    scan["scheduled_incomplete"] = reason == "scheduled_scan_incomplete"
    scan["scheduled_unavailable"] = reason == "scheduled_prompt_unavailable"
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
