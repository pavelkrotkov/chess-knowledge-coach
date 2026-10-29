"""Process one learner position with sanitized progress reporting."""

from .material_context import NotLearnerDecision
from .pawn_coach_detector import process_decision


def process_item(db, position_id, learner, report, outcomes):
    try:
        result = process_decision(db, position_id, learner)
    except NotLearnerDecision:
        return
    except Exception:
        report["unavailable"] += 1
        return
    if result["skipped"]:
        return
    report["processed"] += 1
    report["replayed"] += int(result["replayed"])
    outcomes[result["outcome"]] += 1
