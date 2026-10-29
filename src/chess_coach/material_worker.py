"""Process bounded learner material observations without rerunning analysis."""

from collections import Counter

from .material_worker_cursor import advance, scan
from .material_worker_item import process_item


def process_material(db, config):
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
    key, rows = scan(db, config.learner, config.material_max_scan)
    outcomes = Counter()
    for row in rows[: config.material_max_scan]:
        if report["processed"] >= config.material_max_decisions:
            report["capped"] = True
            break
        report["examined"] += 1
        process_item(db, row["id"], config.learner, report, outcomes)
        advance(db, key, row["id"])
    if len(rows) > config.material_max_scan and report["examined"] == config.material_max_scan:
        report["capped"] = True
    if report["capped"] or report["unavailable"]:
        report["status"] = "partial"
    report["outcomes"] = dict(sorted(outcomes.items()))
    return report
