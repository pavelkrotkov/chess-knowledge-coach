"""Process one learner decision and record sanitized progress."""

from .material_source import NotLearnerDecision
from .pawn_structure_publish import publish
from .pawn_structure_source import prepare_lesson


def process_item(db, position_id, learner, report, outcomes):
    try:
        prepared, fact = prepare_lesson(db, position_id, learner)
        run = publish(db, prepared, fact)
    except NotLearnerDecision:
        return
    except Exception:
        report["unavailable"] += 1
        return
    if run["replayed"]:
        report["replayed"] += 1
    else:
        report["processed"] += 1
        outcomes["descriptive" if fact else "no_match"] += 1
