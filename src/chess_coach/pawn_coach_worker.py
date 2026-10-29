"""Run bounded, independent automatic pawn-endgame observations."""

from collections import Counter

from .pawn_coach_worker_cursor import POLICY, scan
from .pawn_coach_worker_item import process_item
from .pipeline_cursor import save_cursor


def process_pawns(db, config):
    report = {
        "status": "disabled",
        "examined": 0,
        "processed": 0,
        "replayed": 0,
        "unavailable": 0,
        "capped": False,
        "outcomes": {},
        "limits": {"positions": config.pawn_max_scan, "decisions": config.pawn_max_decisions},
    }
    if not config.pawn_enabled:
        return report
    report["status"] = "complete"
    key, rows = scan(db, config.learner, config.pawn_max_scan)
    outcomes = Counter()
    for row in rows[: config.pawn_max_scan]:
        if report["processed"] + report["unavailable"] >= config.pawn_max_decisions:
            report["capped"] = True
            break
        report["examined"] += 1
        process_item(db, row["id"], config.learner, report, outcomes)
        save_cursor(db, key, row["id"], POLICY)
    if len(rows) > config.pawn_max_scan and report["examined"] == config.pawn_max_scan:
        report["capped"] = True
    if report["capped"] or report["unavailable"]:
        report["status"] = "partial"
    report["outcomes"] = dict(sorted(outcomes.items()))
    return report
