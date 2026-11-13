"""Resolve owned and optional unfamiliar chapters under separate work bounds."""

from .tactical_course_budget import PreviewUnavailable
from .tactical_course_chapters import owned
from .tactical_course_deadline import PreviewDeadline
from .tactical_course_evidence import independent
from .tactical_course_familiar import familiarity
from .tactical_course_familiar_games import FamiliarityLimit
from .tactical_course_protection import ContextUnavailable
from .tactical_course_protection import source as teaching_source
from .tactical_course_related import HISTORY_LIMIT, PROTECTION_SOURCE, with_reason


def own(db, subject, group, budget):
    try:
        bindings = None
        lesson = group["lesson"]
        if lesson["skill"] == "fork" or (lesson["skill"], lesson["operation"]) == (
            "hanging_piece",
            "prevent",
        ):
            # Keep both source checks within the shared versioned course budget.
            with budget.scope(snapshot=True):
                bindings = independent(db, subject, group)
        with budget.scope(snapshot=True):
            return owned(db, subject, group, bindings=bindings)
    except (ValueError, KeyError, TypeError, IndexError):
        raise PreviewUnavailable("lesson source changed") from None


def related(db, subject, corpus, choice, budget):
    try:
        source = None
        if choice["kind"] == "protection":
            with budget.scope(snapshot=True):
                source = teaching_source(db, subject, choice)
        familiar_data = familiarity(db, subject, budget)
        with budget.scope(snapshot=False):
            return with_reason(
                db, subject, corpus, choice, familiar_data=familiar_data, teaching_source=source
            )
    except ContextUnavailable:
        return None, PROTECTION_SOURCE
    except PreviewDeadline:
        budget.check()
        return None, "related matching deferred: time budget"
    except FamiliarityLimit:
        return None, HISTORY_LIMIT
    except (ValueError, KeyError, TypeError, IndexError):
        raise PreviewUnavailable("related source unavailable or changed") from None
