"""Resolve owned and optional unfamiliar chapters under separate work bounds."""

from .tactical_course_budget import PreviewUnavailable
from .tactical_course_chapters import owned
from .tactical_course_deadline import PreviewDeadline
from .tactical_course_related import unfamiliar


def own(db, subject, group, budget):
    with budget.scope(snapshot=True):
        try:
            return owned(db, subject, group)
        except (ValueError, KeyError, TypeError, IndexError):
            raise PreviewUnavailable("lesson source changed") from None


def related(db, subject, corpus, choice, budget):
    if choice["kind"] == "protection":
        return None, "related matching unsupported"
    try:
        with budget.scope(snapshot=False):
            item = unfamiliar(db, subject, corpus, choice)
    except PreviewDeadline:
        budget.check()
        return None, "related matching deferred: time budget"
    except (ValueError, KeyError, TypeError, IndexError):
        raise PreviewUnavailable("related source unavailable or changed") from None
    return item, None if item else "related corpus or compatible unfamiliar example unavailable"
