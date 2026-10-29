"""Rotate through bounded current decisions without engine work."""

from .mate_auto import process_decision
from .mate_worker_cursor import POLICY, scan
from .material_context import NotLearnerDecision
from .pipeline_cursor import save_cursor


def process_mates(db, config):
    report = {
        "status": "disabled",
        "examined": 0,
        "processed": 0,
        "replayed": 0,
        "unavailable": 0,
        "outcomes": {},
        "capped": False,
        "limits": {
            "positions": config.mate_max_scan,
            "decisions": config.mate_max_decisions,
            "nodes_per_decision": 6000,
        },
    }
    if not config.mate_enabled:
        return report
    report["status"] = "complete"
    key, rows = scan(db, config.learner, config.mate_max_scan)
    for row in rows[: config.mate_max_scan]:
        if report["processed"] >= config.mate_max_decisions:
            report["capped"] = True
            break
        report["examined"] += 1
        _item(db, row["id"], config.learner, report)
        save_cursor(db, key, row["id"], POLICY)
    if len(rows) > config.mate_max_scan and report["examined"] == config.mate_max_scan:
        report["capped"] = True
    if report["capped"] or report["unavailable"]:
        report["status"] = "partial"
    return report


def _item(db, position_id, learner, report):
    try:
        result = process_decision(db, position_id, learner)
    except NotLearnerDecision:
        return
    except Exception:
        report["unavailable"] += 1
        return
    report["replayed" if result["replayed"] else "processed"] += 1
    status = result["observation_status"]
    report["outcomes"][status] = report["outcomes"].get(status, 0) + 1
