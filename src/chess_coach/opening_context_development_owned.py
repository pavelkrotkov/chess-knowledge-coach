"""Collect independently reviewed same-side fork-execution misses."""

from collections import Counter

from .opening_context_development_owned_item import observation
from .opening_context_development_owned_summary import summary
from .opening_fork_nomination_owned import MAX_EVIDENCE_ID
from .recurrence_sources import evidence


def collect(db, learner, games, color, budget):
    selected = {game["id"] for game, side in games if side == color}
    with budget.scope(snapshot=False):
        rows, truncated = evidence(
            db, learner, "fork", "execute", MAX_EVIDENCE_ID, failure_only=True
        )
    if truncated:
        return {"status": "withheld", "reason": "evidence_scan_truncated"}
    found, cache, parts, excluded = [], {}, {}, Counter()
    for row in rows:
        if row["game_id"] not in selected:
            continue
        with budget.scope(snapshot=False):
            item = observation(db, learner, row, selected, color, cache, parts, excluded)
        if item is not None:
            found.append(item)
        if excluded["game replay limit"]:
            return {"status": "withheld", "reason": "game_replay_limit"}
    return summary(found, excluded)


def collect_once(cache, db, learner, games, color, budget):
    budget.check()
    if "result" not in cache:
        cache["result"] = collect(db, learner, games, color, budget)
    return cache["result"]
