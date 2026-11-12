"""Advance the established discovered-defense archive cursor."""

from .fork_worker_cursor import scan
from .pipeline_cursor import save_cursor

POLICY = "discovery-mate-defense-worker-v1"
NAMESPACE = "discovery-mate-defense-cursor-v1:"


def work(db, learner, lane, attempt, scan_limit, decision_limit, used):
    lane.update(scanned=True, scan_limit=scan_limit, decision_limit=decision_limit)
    key, positions = scan(db, learner, scan_limit, namespace=NAMESPACE, policy=POLICY)
    for row in positions[:scan_limit]:
        if lane["processed"] >= decision_limit:
            lane["capped"] = True
            break
        lane["examined"] += 1
        if row["id"] in used:
            lane["overlap"] += 1
        else:
            used.add(row["id"])
            attempt(row["id"])
        save_cursor(db, key, row["id"], POLICY)
    if len(positions) > scan_limit and lane["examined"] == scan_limit:
        lane["capped"] = True
