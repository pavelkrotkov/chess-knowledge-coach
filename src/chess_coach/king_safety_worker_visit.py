"""Count only new or unavailable learner work against the decision budget."""

from .king_safety_probe import state
from .king_safety_worker_item import process_item


def visit(db, config, row, report, outcomes):
    status = state(db, row["id"], config.learner)
    if status == "current":
        report["replayed"] += 1
    elif status != "opponent":
        if report["attempted"] >= config.material_max_decisions:
            return False
        report["attempted"] += 1
        if status == "unavailable":
            report["unavailable"] += 1
        else:
            before = report["unavailable"]
            process_item(db, row["id"], config.learner, report, outcomes)
            if (
                report["unavailable"] == before
                and state(db, row["id"], config.learner) != "current"
            ):
                report["unavailable"] += 1
    return True
