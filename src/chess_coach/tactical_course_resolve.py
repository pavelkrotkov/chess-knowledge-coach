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


def own(db, subject, group, budget, *, identity_for=None):
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
            return owned(db, subject, group, bindings=bindings, identity_for=identity_for)
    except PreviewDeadline:
        budget.check()
        return "owned source deferred: time budget"
    except (ValueError, KeyError, TypeError, IndexError):
        raise PreviewUnavailable("lesson source changed") from None


def _source(db, subject, choice, budget, thematic):
    if choice["kind"] != "protection":
        return None
    with budget.scope(snapshot=True):
        try:
            return teaching_source(db, subject, choice)
        except ContextUnavailable:
            if not thematic:
                raise
    return None


def _match(db, subject, corpus, choice, source, familiar_data, thematic, artifact):
    if source is None and choice["kind"] == "protection":
        result = (None, PROTECTION_SOURCE)
    else:
        result = with_reason(
            db, subject, corpus, choice, familiar_data=familiar_data, teaching_source=source
        )
    if thematic and choice["kind"] == "protection":
        from .tactical_course_thematic import fallback

        return fallback(db, subject, corpus, choice, familiar_data, result, artifact=artifact)
    return result


def related(db, subject, corpus, choice, budget, *, thematic=False, artifact=None, named=False):
    try:
        source = _source(db, subject, choice, budget, thematic)
        familiar_data = familiarity(db, subject, budget)
        with budget.scope(snapshot=False):
            if named and choice["kind"] == "capture":
                from .tactical_course_capture import practice

                return practice(db, subject, corpus, choice, familiar_data, artifact=artifact)
            return _match(db, subject, corpus, choice, source, familiar_data, thematic, artifact)
    except ContextUnavailable:
        return None, PROTECTION_SOURCE
    except PreviewDeadline:
        budget.check()
        return None, "related matching deferred: time budget"
    except FamiliarityLimit:
        return None, HISTORY_LIMIT
    except (ValueError, KeyError, TypeError, IndexError):
        raise PreviewUnavailable("related source unavailable or changed") from None
