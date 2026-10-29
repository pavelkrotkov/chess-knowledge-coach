"""Bounded rotating scan of current learner decisions, storing descriptive facts."""

from collections import Counter

from .fork_worker_cursor import scan
from .pawn_structure_worker_item import process_item
from .pipeline_cursor import save_cursor

POLICY = "pawn-structure-worker-v1"


def _scan(db, learner, limit):
    return scan(db, learner, limit, namespace="pawn-structure-worker-cursor-v1:", policy=POLICY)


def process_structure_lessons(db, config):
    report = {
        "status": "disabled",
        "examined": 0,
        "processed": 0,
        "replayed": 0,
        "unavailable": 0,
        "capped": False,
        "outcomes": {},
        "limits": {
            "positions": config.material_max_scan,
            "decisions": config.material_max_decisions,
        },
    }
    if not config.material_enabled:
        return report
    report["status"] = "complete"
    key, rows = _scan(db, config.learner, config.material_max_scan)
    outcomes = Counter()
    limit = min(config.material_max_scan, config.material_max_decisions)
    for row in rows[:limit]:
        report["examined"] += 1
        process_item(db, row["id"], config.learner, report, outcomes)
        save_cursor(db, key, row["id"], POLICY)
    report["capped"] = len(rows) > limit
    if report["capped"] or report["unavailable"]:
        report["status"] = "partial"
    report["outcomes"] = dict(sorted(outcomes.items()))
    return report
