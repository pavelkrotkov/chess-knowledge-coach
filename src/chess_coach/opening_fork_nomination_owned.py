"""Collect current fork execution observations after a selected branch."""

from collections import Counter

from .opening_fork_nomination_check import checked
from .recurrence_sources import evidence

MAX_EVIDENCE_ID = (1 << 63) - 1


def observations(db, learner, selected, budget):
    branches = {item["game_id"]: item for item in selected}
    with budget.scope(snapshot=False):
        rows, truncated = evidence(
            db, learner, "fork", "execute", MAX_EVIDENCE_ID, game_ids=list(branches)
        )
    if truncated:
        return None
    found, seen, cache, parts, excluded = [], set(), {}, {}, Counter()
    for row in rows:
        if row["game_id"] not in branches or row["ply"] <= branches[row["game_id"]]["ply"]:
            continue
        with budget.scope(snapshot=False):
            item = checked(db, learner, row, branches, cache, parts, excluded)
        if item is None:
            return None
        key = (item["game_key"], item["position_id"])
        if key in seen:
            return None
        seen.add(key)
        found.append(item)
    return found
