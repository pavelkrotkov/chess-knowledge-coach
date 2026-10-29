"""Bounded, subject-owned material practice candidates."""

from collections import Counter

from .learner_identity import normalize_identity
from .preview_snapshot import preview_history
from .unified_own_game_evidence import LIMIT, _inspect, _rows
from .unified_own_game_snapshot import group_for, key_for

VERSION = "material-own-v2"
LEGACY_VERSION = "material-own-v1"


def list_candidates(db, subject):
    if not normalize_identity(subject):
        return {
            "version": VERSION,
            "candidates": [],
            "excluded": {"subject unavailable": 1},
            "scanned": 0,
            "truncated": False,
        }
    with preview_history(db, subject) as history:
        return _list(db, subject, history)


def _list(db, subject, history):
    rows = _rows(db, subject)
    history.targets(row["position_id"] for row in rows[:LIMIT])
    ready = {}
    excluded = Counter()
    for row in rows[:LIMIT]:
        view, _, reasons = _inspect(db, row["id"], subject, history)
        if reasons:
            excluded.update(reasons)
        else:
            group = group_for(view)
            ready.setdefault(
                group,
                {
                    "key": key_for(view, row["id"]),
                    "objective": view["objective"]["kind"],
                    "review_status": view["review_status"],
                },
            )
    return {
        "version": VERSION,
        "candidates": list(ready.values()),
        "excluded": dict(excluded),
        "scanned": min(len(rows), LIMIT),
        "truncated": len(rows) > LIMIT,
    }
