"""Keep tactical version intents separate and unresolved creates exclusive."""

from itertools import islice

from .study_remote import StudyError
from .tactical_export_input import _read

MAX_INTENTS = 100


def _pending(path):
    state = _read(path)
    if (
        not isinstance(state, dict)
        or "study" not in state
        or type(state.get("create_pending")) is not bool
    ):
        raise StudyError("Study intent cannot be verified")
    if state.get("study") is not None and not isinstance(state["study"], str):
        raise StudyError("Study intent cannot be verified")
    return state["create_pending"] and state.get("study") is None


def intent(planning, course_hash):
    path = planning / f"tactical-study-{course_hash}-intent.json"
    paths = list(islice(planning.glob("tactical-study-*-intent.json"), MAX_INTENTS + 1))
    if len(paths) + (path not in paths) > MAX_INTENTS:
        raise StudyError("too many tactical Study intents")
    previous = planning / "poc-study-336-intent.json"
    if previous.exists() and _pending(previous):
        raise StudyError("previous Study creation outcome remains unresolved")
    for other in paths:
        pending = _pending(other)
        if other != path and pending:
            raise StudyError("another tactical Study creation outcome remains unresolved")
    return path
