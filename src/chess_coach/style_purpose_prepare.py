"""Collect bounded purpose slots and preserve sample-exclusion coverage."""

from collections import defaultdict

from .style_purpose_counts import coverage_counts
from .style_purpose_slots import slots


def prepare(db, learner, games):
    rows, limits = slots(db, learner)
    contexts = {
        game["game_id"]: {item["position_id"]: item for item in game["contexts"]} for game in games
    }
    grouped = defaultdict(list)
    counts = coverage_counts()
    for row in rows:
        kind = row["kind"]
        counts[f"{kind}_slots"] += 1
        if row["game_id"] not in contexts:
            counts[f"{kind}_outside_sample"] += 1
        elif row["position_id"] not in contexts[row["game_id"]]:
            counts[f"{kind}_context_unknown"] += 1
        elif row["request_id"] is None:
            state = (
                "pending"
                if row["status"] in ("ready", "pending", "running", "interrupted")
                else "unknown"
            )
            counts[f"{kind}_{state}"] += 1
        else:
            grouped[row["game_id"]].append(row)
    return {
        "grouped": grouped,
        "contexts": contexts,
        "counts": counts,
        "limits": limits,
        "views": {},
        "observations": [],
    }


def required_ids(selected, rows):
    ids = {row["position_id"] for row in rows}
    if selected is not None:
        ids.update(item["position_id"] for item in selected["items"])
    return ids
