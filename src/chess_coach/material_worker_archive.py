"""Advance the original material archive cursor under the remaining budget."""

from .material_worker_cursor import advance, scan
from .material_worker_item import process_item


def work(db, config, report, outcomes, exclude):
    limit = config.material_max_scan - report["examined"]
    key, rows = scan(db, config.learner, limit)
    examined = 0
    for row in rows[:limit]:
        if report["processed"] >= config.material_max_decisions:
            report["capped"] = True
            break
        examined += 1
        report["examined"] += 1
        if row["id"] not in exclude:
            process_item(db, row["id"], config.learner, report, outcomes)
        advance(db, key, row["id"])
    if len(rows) > limit and examined == limit:
        report["capped"] = True
