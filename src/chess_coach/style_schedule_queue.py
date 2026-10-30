"""Choose at most three oldest independent purpose jobs fairly."""

from .deep_selection_source import learner_key
from .style_protection_schedule_store import pending as protection_pending
from .style_schedule_slots import pending as standard_pending

MAX_JOBS = 3
PRIORITY = {"target": 0, "control": 1, "protection": 2}


def pending(db, learner):
    standard = [dict(row) for row in standard_pending(db, learner)]
    protection = [
        {**dict(row), "kind": "protection"} for row in protection_pending(db, learner_key(learner))
    ]
    return sorted(standard + protection, key=lambda row: (row["sequence"], PRIORITY[row["kind"]]))[
        :MAX_JOBS
    ]
