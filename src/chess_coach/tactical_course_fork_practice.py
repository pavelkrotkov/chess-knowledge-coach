"""Build and recheck a certified unfamiliar fork course exercise."""

from itertools import islice

from .related_fork import selection
from .related_fork_assessment_search import PROOFS, ROWS
from .tactical_course_budget import PreviewUnavailable
from .tactical_course_deadline import PreviewDeadline
from .tactical_course_familiar import familiarity
from .tactical_course_familiar_games import FamiliarityLimit
from .tactical_course_fork_exercise import chapter
from .tactical_course_related import FORK_CORPUS, FORK_EMPTY, HISTORY_LIMIT
from .tactical_course_thematic_exposure import exposure


def related(db, subject, corpus, choice, budget, *, artifact=None, saved=None):
    try:
        return _practice(db, subject, corpus, choice, budget, artifact=artifact, saved=saved)
    except PreviewDeadline:
        budget.check()
        return None, "related matching deferred: time budget"
    except FamiliarityLimit:
        return None, HISTORY_LIMIT
    except (ValueError, KeyError, TypeError, IndexError):
        raise PreviewUnavailable("related source unavailable or changed") from None


def _practice(db, subject, corpus, choice, budget, *, artifact=None, saved=None):
    familiar_data = familiarity(db, subject, budget)
    check = budget.check
    with budget.scope(snapshot=False):
        selected = selection(
            db, subject, choice["evidence_id"], corpus, familiar_data=familiar_data
        )
        if selected is None:
            return None, FORK_CORPUS
        if selected[0]["provenance"]["evidence_id"] != choice["evidence_id"]:
            raise ValueError("related source differs from selected lesson")
        if selected[0]["outcome"] != "failure":
            return None, FORK_EMPTY
        # Saved reads rebind the worker's independent proof record instead of certifying again.
        for item in islice(_candidates(db, subject, selected[3], artifact, saved, check), PROOFS):
            try:
                return chapter(db, subject, selected, item, choice, saved, check), None
            except (ValueError, TypeError, KeyError, IndexError):
                check()
        return None, FORK_EMPTY


def _candidates(db, subject, ordered, artifact, saved, check):
    for item in ordered[:ROWS]:
        check()
        if item["type"] != "corpus":
            continue
        if saved is not None and (item["version"], item["key"]) != (saved["version"], saved["key"]):
            continue
        if exposure(db, subject, item["prompt_key"], artifact) == "not_recorded":
            yield item
