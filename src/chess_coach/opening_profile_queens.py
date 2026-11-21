"""Count bounded observed queen states in selected public games."""

from collections import Counter

from .opening_profile_queen_replay import replay


def summarize(db, rows, decision, move, deadline):
    counts = Counter()
    for game_id, total, _context in rows:
        item = replay(db, game_id, total, decision, move, deadline)
        counts[item["status"]] += 1
        if item.get("start") is not None:
            counts[item["start"]] += 1
        counts["queenless_observed"] += item["queenless_observed"]
        counts["one_or_imbalanced"] += item["one_or_imbalanced"]
    return {
        "sampled": len(rows),
        "replay_supported": counts["ended"] + counts["frontier"] + counts["cutoff"],
        **{
            key: counts[key]
            for key in (
                "one_each",
                "preexisting_queenless",
                "start_imbalanced",
                "queenless_observed",
                "one_or_imbalanced",
                "ended",
                "frontier",
                "cutoff",
                "unsupported",
                "unavailable",
            )
        },
    }
