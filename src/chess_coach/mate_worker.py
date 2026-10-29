"""Rotate through bounded current decisions without engine work."""

from .back_rank_worker_item import process as process_back_rank
from .mate_auto import process_decision
from .mate_worker_cursor import POLICY, scan
from .mate_worker_report import finish, initial
from .material_context import NotLearnerDecision
from .pipeline_cursor import save_cursor


def process_mates(db, config):
    report = initial(config)
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
    return finish(report)


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
    process_back_rank(db, position_id, learner, report["back_rank"])
