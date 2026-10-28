"""Advance bounded corpus and scheduled-prompt conflict scans."""

from .curriculum_candidates import verified_candidate
from .curriculum_consider import check_pending, consider
from .curriculum_new import new_page
from .db import Database


def scan_new(db: Database, state: dict, summary: dict) -> tuple[list[dict], dict, str | None]:
    rows = new_page(db, state["corpus_version"], state["new_after"], state["scan_limit"])
    if state["pending"] is not None and not rows:
        raise ValueError("curriculum candidate changed; restart the plan")
    selected = []
    seen = set(state["seen"])
    counts = {"corpus_examined": 0, "scheduled_examined": 0, "scheduled_unavailable_item_id": None}
    for row in rows[: state["scan_limit"]]:
        if len(row["puzzle_id"]) > 256:
            raise ValueError("puzzle ID is too long for bounded continuation")
        counts["corpus_examined"] += 1
        candidate = verified_candidate(row)
        check_pending(state, row, candidate)
        reason, items, seen = consider(db, state, row, candidate, summary, seen, counts)
        selected.extend(items)
        if reason is not None:
            state["seen"] = sorted(seen)
            return selected, counts, reason
        state["new_after"] = [row["rating"], row["puzzle_id"]]
        if len(seen) >= state["limit"]:
            state["seen"] = sorted(seen)
            return selected, counts, None
    state["seen"] = sorted(seen)
    return selected, counts, "corpus_scan_incomplete" if len(rows) > state["scan_limit"] else None
