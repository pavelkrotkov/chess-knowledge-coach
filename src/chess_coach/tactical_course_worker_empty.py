"""Record an empty selected preparation without publishing an artifact."""

from .tactical_course_choice import pairs
from .tactical_course_readiness import selection
from .tactical_course_selection import CURRENT_PAIRS
from .tactical_course_worker_state import failed


def record_empty(directory, database, learner, corpus, requested, old_offer, budget, candidate):
    raw = candidate["preview"]["selection"]
    selected = requested.get("selection")
    chosen = CURRENT_PAIRS if selected is None else pairs(selected)
    failed(
        directory,
        database,
        learner,
        corpus,
        requested,
        selection=selection(raw["coverage"], raw["unavailable"], chosen),
        old_offer=old_offer,
        budget=budget,
    )


def record_diagnostic(directory, database, learner, corpus, requested, old_offer, budget, result):
    failed(
        directory,
        database,
        learner,
        corpus,
        requested,
        selection=result.selection,
        old_offer=old_offer,
        budget=budget,
    )


def require_chapters(result):
    if not result["export"]["chapters"]:
        raise ValueError("no supported chapters")
