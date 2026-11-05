"""Keep tactical version intents separate and unresolved creates exclusive."""

from itertools import islice

from .study_remote import StudyError
from .tactical_study_intent_status import pending

MAX_INTENTS = 100


def require_clear(planning, current):
    paths = list(islice(planning.glob("tactical-study-*-intent.json"), MAX_INTENTS + 1))
    if len(paths) > MAX_INTENTS:
        raise StudyError("too many tactical Study intents")
    previous = planning / "poc-study-336-intent.json"
    if previous != current and previous.exists() and pending(previous):
        raise StudyError("previous Study creation outcome remains unresolved")
    for other in paths:
        is_pending = pending(other)
        if other != current and is_pending:
            raise StudyError("another tactical Study creation outcome remains unresolved")
    return paths


def intent(planning, course_hash):
    path = planning / f"tactical-study-{course_hash}-intent.json"
    paths = require_clear(planning, path)
    if len(paths) + (path not in paths) > MAX_INTENTS:
        raise StudyError("too many tactical Study intents")
    return path
