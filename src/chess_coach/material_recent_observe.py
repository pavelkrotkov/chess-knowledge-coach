"""Count one exact material result without exposing its source."""

from .material_recent_cursor import save
from .material_worker_item import process_item


def observe(db, learner, row, state, report, outcomes, recent):
    report["examined"] += 1
    recent["examined"] += 1
    before = report["unavailable"]
    result = process_item(db, row["id"], learner, report, outcomes)
    if result is None:
        recent["unavailable"] += report["unavailable"] - before
    else:
        recent["replayed"] += int(result["replayed"])
        recent["processed"] += int(not result["replayed"])
        name = "no_opportunity" if result["outcome"] == "no_opportunity" else "observed"
        recent[name] += 1
    state = {**state, "ply": row["ply"]}
    save(db, learner, state)
    return state
