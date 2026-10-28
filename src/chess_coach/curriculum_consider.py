"""Revalidate and check one new puzzle against scheduled prompts."""

from .curriculum_conflicts import scheduled_page
from .curriculum_selection import select
from .db import Database
from .fact_fingerprint import digest


def check_pending(state: dict, row, candidate: dict | None) -> None:
    pending = state["pending"]
    if pending is None:
        return
    expected = [
        row["rating"],
        row["puzzle_id"],
        digest(candidate["prompt_key"]) if candidate else "",
    ]
    if pending != expected:
        raise ValueError("curriculum candidate changed; restart the plan")


def consider(
    db: Database,
    state: dict,
    row,
    candidate: dict | None,
    summary: dict,
    seen: set[str],
    counts: dict,
) -> tuple[str | None, list[dict], set[str]]:
    if candidate is None or candidate["prompt_key"] in seen:
        _clear_pending(state)
        return None, [], seen
    budget = state["scan_limit"] - counts["scheduled_examined"]
    matched, after, more, examined, unavailable = scheduled_page(
        db, candidate["prompt_key"], state["scheduled_after"], budget
    )
    counts["scheduled_examined"] += examined
    if unavailable is not None:
        counts["scheduled_unavailable_item_id"] = unavailable
        return "scheduled_prompt_unavailable", [], seen
    if more:
        state["pending"] = [row["rating"], row["puzzle_id"], digest(candidate["prompt_key"])]
        state["scheduled_after"] = after
        return "scheduled_scan_incomplete", [], seen
    _clear_pending(state)
    if matched:
        return None, [], seen
    entry = {**candidate, "kind": "new", "item_id": None, "due": None}
    items, seen = select([entry], state["limit"] - len(seen), summary, seen)
    return None, items, seen


def _clear_pending(state: dict) -> None:
    state["pending"] = None
    state["scheduled_after"] = 0
