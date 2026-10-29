"""Run back-rank observation within the bounded mate cursor."""

from .back_rank_auto import process_decision


def process(db, position_id, learner, report):
    report["attempted"] += 1
    try:
        result = process_decision(db, position_id, learner)
    except Exception:
        report["unavailable"] += 1
        return
    report["replayed" if result["replayed"] else "processed"] += 1
    status = result["observation_status"]
    report["outcomes"][status] = report["outcomes"].get(status, 0) + 1
