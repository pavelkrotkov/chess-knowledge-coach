"""Bounded schedule lookup for a due candidate."""

from typing import TypeGuard

from .curriculum_schedule import due_schedule_page
from .db import Database


def check_schedule(db: Database, state: dict, candidate: dict, scan: dict) -> str | None:
    budget = state["scan_limit"] - scan["scheduled_examined"]
    best, after, more, count, unavailable = due_schedule_page(
        db, candidate["prompt_key"], state["scheduled_after"], budget, state["scheduled_best"]
    )
    scan["scheduled_examined"] += count
    state["scheduled_best"], state["scheduled_after"] = best, after
    if unavailable is not None:
        scan["scheduled_unavailable"] = True
        scan["scheduled_unavailable_item_id"] = unavailable
        return "scheduled_prompt_unavailable"
    if more:
        scan["scheduled_incomplete"] = True
        return "scheduled_scan_incomplete"
    return None


def eligible(candidate: dict | None, seen: set[str]) -> TypeGuard[dict]:
    return candidate is not None and candidate["prompt_key"] not in seen
