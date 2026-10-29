"""Summarize bounded current selections for a private learner status page."""

from collections import Counter

from .deep_selection_source import learner_key
from .deep_selection_views import list_selections, show_selection
from .fact_fingerprint import digest
from .pipeline_deep_counts import selection_counts
from .pipeline_deep_cursor import _record

STATUS_SCAN_LIMIT = 25


def deep_status(db, learner):
    if not learner:
        return None
    try:
        selections = list_selections(db, learner, limit=STATUS_SCAN_LIMIT)
    except ValueError:
        return None
    counts = Counter(
        {"selected": 0, "pending": 0, "capped_out": 0, "insufficient": 0, "unstable": 0}
    )
    for row in selections:
        selection = show_selection(db, row["game_id"], learner)
        if selection["state"] != "current":
            counts["stale_selections"] += 1
            continue
        counts["games"] += 1
        counts.update(selection_counts(selection))
    return {
        "limits": _limits(db, learner),
        "counts": dict(sorted(counts.items())),
        "examined_games": len(selections),
        "scan_limit": STATUS_SCAN_LIMIT,
        "truncated": len(selections) == STATUS_SCAN_LIMIT,
    }


def _limits(db, learner):
    key = digest("automatic-deep-cursor-v1:" + learner_key(learner))
    row = db.connection.execute(
        "SELECT scan_hash FROM pipeline_cursors WHERE account_key=?", (key,)
    ).fetchone()
    return _record(row[0]).get("limits") if row else None
