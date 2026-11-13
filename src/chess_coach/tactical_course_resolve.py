"""Resolve owned and optional unfamiliar chapters under separate work bounds."""

from .tactical_course_budget import PreviewUnavailable
from .tactical_course_chapters import owned
from .tactical_course_deadline import PreviewDeadline
from .tactical_course_evidence import independent
from .tactical_course_familiar import familiarity
from .tactical_course_familiar_games import FamiliarityLimit
from .tactical_course_related import GENERAL_EMPTY, HISTORY_LIMIT, unfamiliar, with_reason


def own(db, subject, group, budget):
    try:
        bindings = None
        if group["lesson"]["skill"] == "fork":
            # Keep both source checks within the shared versioned course budget.
            with budget.scope(snapshot=True):
                bindings = independent(db, subject, group)
        with budget.scope(snapshot=True):
            return owned(db, subject, group, bindings=bindings)
    except (ValueError, KeyError, TypeError, IndexError):
        raise PreviewUnavailable("lesson source changed") from None


def related(db, subject, corpus, choice, budget):
    if choice["kind"] == "protection":
        return None, "related matching unsupported"
    try:
        familiar_data = familiarity(db, subject, budget)
        with budget.scope(snapshot=False):
            if choice["kind"] == "fork":
                return with_reason(db, subject, corpus, choice, familiar_data=familiar_data)
            item = unfamiliar(db, subject, corpus, choice, familiar_data=familiar_data)
    except PreviewDeadline:
        budget.check()
        return None, "related matching deferred: time budget"
    except FamiliarityLimit:
        return None, HISTORY_LIMIT
    except (ValueError, KeyError, TypeError, IndexError):
        raise PreviewUnavailable("related source unavailable or changed") from None
    return item, None if item else GENERAL_EMPTY
