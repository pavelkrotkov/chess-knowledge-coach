"""Bounded rotating scan of current learner decisions, storing descriptive facts."""

from collections import Counter

from .fork_worker_cursor import scan
from .pipeline_cursor import save_cursor
from .rook_plan_worker_report import new_report
from .rook_plan_worker_visit import visit

POLICY = "rook-plan-worker-v1"


def _scan(db, learner, limit):
    return scan(db, learner, limit, namespace="rook-plan-worker-cursor-v1:", policy=POLICY)


def process_rook_plans(db, config):
    report = new_report(config)
    if not config.material_enabled:
        return report
    report["status"] = "complete"
    key, rows = _scan(db, config.learner, config.material_max_scan)
    outcomes = Counter()
    for row in rows[: config.material_max_scan]:
        report["examined"] += 1
        if not visit(db, config, row, report, outcomes):
            report["pending"] = True
            break
        save_cursor(db, key, row["id"], POLICY)
    report["scan_limited"] = len(rows) > config.material_max_scan
    report["capped"] = report["pending"] or report["scan_limited"]
    if report["capped"] or report["unavailable"]:
        report["status"] = "partial"
    report["outcomes"] = dict(sorted(outcomes.items()))
    return report
