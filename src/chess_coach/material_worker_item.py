"""Process one scanned position and record only sanitized progress."""

from .material_detector import process_decision
from .material_source import NotLearnerDecision


def process_item(db, position_id, learner, report, outcomes):
    try:
        result = process_decision(db, position_id, learner)
    except NotLearnerDecision:
        return
    except Exception:
        report["unavailable"] += 1
        return
    if result["replayed"]:
        report["replayed"] += 1
    else:
        report["processed"] += 1
        outcomes[result["outcome"]] += 1
