"""Resume bounded recent polling and rotating full-history reconciliation."""

from __future__ import annotations

from .db import Database
from .lichess_commit import apply_window, split_progress
from .lichess_progress import prepare_progress
from .lichess_step import fetch_step, validate_limits
from .lichess_windows import Exporter, choose_field


def sync(
    client: Exporter,
    db: Database,
    username: str,
    *,
    max_games: int,
    page_size: int,
    since: int | None,
    now: int,
) -> dict:
    since = validate_limits(max_games, page_size, since, now)
    state = prepare_progress(db, username, since, now)
    totals = {"games": 0, "positions": 0, "unsupported": 0}
    budget = min(50, max(4, max_games))
    requests = 0
    blocked = False
    for index in range(budget):
        if totals["games"] >= max_games:
            break
        field = choose_field(state, index)
        if field is None:
            break
        remaining = max_games - totals["games"]
        records, children, calls, blocked = fetch_step(
            client, username, state[field][0], remaining, page_size
        )
        requests += calls
        if blocked:
            break
        if children is not None:
            split_progress(db, state, field, children)
            continue
        result = apply_window(db, state, field, records)
        for key in totals:
            totals[key] += result[key]
    return {
        **totals,
        "requests": requests,
        "history_cycles": state["history_cycles"],
        "bootstrap_complete": state["history_cycles"] > 0,
        "recent_complete": not state["recent_windows"],
        "history_complete": not state["history_windows"],
        "blocked_saturated": blocked,
    }
