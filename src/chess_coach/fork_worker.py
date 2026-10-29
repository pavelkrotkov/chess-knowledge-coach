"""Bounded independent scan for provisional fork observations."""

from collections import Counter

from .fork_worker_cursor import POLICY, scan
from .fork_worker_item import process_item
from .pipeline_cursor import save_cursor


def process_forks(db, config):
    report = {
        "status": "complete",
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
    key, rows = scan(db, config.learner, config.material_max_scan)
    outcomes = Counter()
    for row in rows[: config.material_max_scan]:
        if report["processed"] >= config.material_max_decisions:
            report["capped"] = True
            break
        report["examined"] += 1
        process_item(db, row["id"], config.learner, report, outcomes)
        save_cursor(db, key, row["id"], POLICY)
    if len(rows) > config.material_max_scan and report["examined"] == config.material_max_scan:
        report["capped"] = True
    if report["capped"] or report["unavailable"]:
        report["status"] = "partial"
    report["outcomes"] = dict(sorted(outcomes.items()))
    return report
